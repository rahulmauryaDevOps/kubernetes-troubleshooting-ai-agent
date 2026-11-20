from contextlib import asynccontextmanager
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.agents.langgraph_workflow import build_workflow
from app.agents.slack_notifier import send_slack_alert
from app.collectors.pod_watcher import PodWatcher


def notify_slack(message):
    """Send Slack notification without interrupting the main workflow."""
    try:
        result = send_slack_alert(message)
        if not result:
            print("Slack notification was not confirmed.")
        return result
    except Exception as exc:
        print(f"Slack notification failed: {exc}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    with SqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
        app.state.agent = build_workflow(checkpointer)
        app.state.agent_lock = Lock()
        app.state.incidents = []
        app.state.incidents_lock = Lock()

        def handle_incident(incident):
            thread_id = str(uuid4())
            config = {"configurable": {"thread_id": thread_id}}

            namespace = incident.get("namespace", "unknown")
            pod = incident.get("pod", "unknown")
            reason = incident.get("reason", "unknown")
            container = incident.get("container", "unknown")

            notify_slack(
                f"🚨 *KUBERNETES INCIDENT DETECTED*\n"
                f"*Namespace:* `{namespace}`\n"
                f"*Pod:* `{pod}`\n"
                f"*Container:* `{container}`\n"
                f"*Reason:* `{reason}`\n"
                f"*Thread ID:* `{thread_id}`"
            )

            try:
                with app.state.agent_lock:
                    result = app.state.agent.invoke(
                        {"incident_context": incident},
                        config=config
                    )

                interrupts = result.get("__interrupt__", [])

                record = {
                    "thread_id": thread_id,
                    "incident": incident,
                    "status": (
                        "awaiting_human_review" if interrupts
                        else result.get("status")
                    ),
                    "classification": result.get("classification"),
                    "ai_explanation": result.get("ai_explanation"),
                    "recommendation": result.get("recommendation"),
                    "approval_request": (
                        interrupts[0].value if interrupts else None
                    )
                }

                if interrupts:
                    explanation = str(
                        result.get("ai_explanation", "Not available")
                    )[:2500]

                    recommendation = str(
                        result.get("recommendation", "Manual review required")
                    )[:1000]

                    notify_slack(
                        f"🤖 *AI ANALYSIS COMPLETED — APPROVAL PENDING*\n"
                        f"*Pod:* `{pod}`\n"
                        f"*Reason:* `{reason}`\n"
                        f"*AI Analysis:*\n{explanation}\n"
                        f"*Recommendation:*\n{recommendation}\n"
                        f"*Thread ID:* `{thread_id}`\n"
                        f"⚠️ Review the dashboard before approving remediation."
                    )
                else:
                    notify_slack(
                        f"ℹ️ *INCIDENT ANALYSIS COMPLETED*\n"
                        f"*Pod:* `{pod}`\n"
                        f"*Status:* `{result.get('status')}`\n"
                        f"*Thread ID:* `{thread_id}`"
                    )

            except Exception as exc:
                record = {
                    "thread_id": thread_id,
                    "incident": incident,
                    "status": "error",
                    "error": str(exc)
                }

                notify_slack(
                    f"❌ *AI WORKFLOW ERROR*\n"
                    f"*Pod:* `{pod}`\n"
                    f"*Error:* `{str(exc)[:1000]}`\n"
                    f"*Thread ID:* `{thread_id}`"
                )

            with app.state.incidents_lock:
                app.state.incidents.append(record)

        watcher = PodWatcher(on_incident=handle_incident)
        watcher.start()

        try:
            yield
        finally:
            watcher.stop()


app = FastAPI(
    title="Kubernetes Troubleshooting AI Agent",
    description="AI-powered Kubernetes diagnostics and approved remediation",
    version="1.3.0",
    lifespan=lifespan
)


class ApprovalRequest(BaseModel):
    decision: str = Field(description="approve or reject")


@app.get("/")
def root():
    return {
        "message": "Kubernetes Troubleshooting AI Agent API is running",
        "status": "healthy"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/incidents")
def get_incidents(request: Request):
    with request.app.state.incidents_lock:
        return {
            "total": len(request.app.state.incidents),
            "incidents": list(request.app.state.incidents)
        }


@app.post("/troubleshoot")
def troubleshoot(request: Request):
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    try:
        with request.app.state.agent_lock:
            result = request.app.state.agent.invoke({}, config=config)

        if result.get("status") == "error":
            raise HTTPException(
                status_code=500,
                detail=result.get("error")
            )

        interrupts = result.get("__interrupt__", [])

        if interrupts:
            return {
                "thread_id": thread_id,
                "status": "awaiting_human_review",
                "classification": result.get("classification"),
                "diagnostics": result.get("diagnostics"),
                "ai_explanation": result.get("ai_explanation"),
                "recommendation": result.get("recommendation"),
                "approval_request": interrupts[0].value
            }

        return {
            "thread_id": thread_id,
            "status": result.get("status"),
            "classification": result.get("classification"),
            "diagnostics": result.get("diagnostics")
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/approve/{thread_id}")
def approve(thread_id: str, body: ApprovalRequest, request: Request):
    decision = body.decision.strip().lower()

    if decision not in ("approve", "reject"):
        raise HTTPException(
            status_code=400,
            detail="Decision must be approve or reject"
        )

    config = {"configurable": {"thread_id": thread_id}}

    try:
        with request.app.state.agent_lock:
            result = request.app.state.agent.invoke(
                Command(resume=decision),
                config=config
            )

        remediation = result.get("remediation_result") or {}

        response = {
            "thread_id": thread_id,
            "approval_decision": result.get("approval_decision"),
            "status": result.get("status"),
            "remediation_result": remediation,
            "resources_modified": (
                remediation.get("status") == "success"
            )
        }

        with request.app.state.incidents_lock:
            for record in request.app.state.incidents:
                if record["thread_id"] == thread_id:
                    record.update(response)

        if decision == "reject":
            notify_slack(
                f"🛑 *REMEDIATION REJECTED*\n"
                f"*Thread ID:* `{thread_id}`\n"
                f"*Status:* `{result.get('status')}`\n"
                f"No remediation was approved."
            )

        elif remediation.get("status") == "success":
            notify_slack(
                f"✅ *REMEDIATION SUCCESSFUL*\n"
                f"*Deployment:* `{remediation.get('deployment')}`\n"
                f"*Namespace:* `{remediation.get('namespace')}`\n"
                f"*Old Image:* `{remediation.get('old_image')}`\n"
                f"*New Image:* `{remediation.get('new_image')}`\n"
                f"*Verification:* {remediation.get('verification')}\n"
                f"*Thread ID:* `{thread_id}`"
            )

        else:
            notify_slack(
                f"❌ *REMEDIATION FAILED OR NOT COMPLETED*\n"
                f"*Thread ID:* `{thread_id}`\n"
                f"*Status:* `{result.get('status')}`\n"
                f"*Details:* {str(remediation)[:1500]}"
            )

        return response

    except Exception as exc:
        notify_slack(
            f"❌ *APPROVAL WORKFLOW ERROR*\n"
            f"*Thread ID:* `{thread_id}`\n"
            f"*Error:* `{str(exc)[:1000]}`"
        )
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/cluster-health")
def cluster_health():
    from app.collectors.cluster_health import get_cluster_health

    try:
        return get_cluster_health()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
