import time
from typing import TypedDict

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

from app.agents.k8sgpt_engine import run_k8sgpt_analysis
from app.agents.groq_engine import explain_findings


class TroubleshootingState(TypedDict, total=False):
    incident_context: dict
    diagnostics: dict
    classification: str
    ai_explanation: str
    recommendation: str
    approval_decision: str
    remediation_result: dict
    status: str
    error: str


def diagnostic_node(state):
    incident = state.get("incident_context")

    if incident:
        findings = {
            "problems": 1,
            "source": "Kubernetes Watch API",
            "findings": [incident]
        }
        return {
            "diagnostics": findings,
            "status": "diagnostics_completed"
        }

    result = run_k8sgpt_analysis()

    if result.get("status") != "success":
        return {
            "status": "error",
            "error": result.get("message", "Diagnostic failed")
        }

    return {
        "diagnostics": result["findings"],
        "status": "diagnostics_completed"
    }


def classification_node(state):
    problems = state["diagnostics"].get("problems", 0)
    return {
        "classification": "HEALTHY" if problems == 0 else "REQUIRES_REVIEW",
        "status": "classification_completed"
    }


def ai_analysis_node(state):
    explanation = explain_findings(state["diagnostics"])
    return {
        "ai_explanation": explanation,
        "status": "analysis_completed"
    }


def recommendation_node(state):
    incident = state.get("incident_context", {})

    if (
        incident.get("namespace") == "default"
        and incident.get("pod", "").startswith("image-test-")
        and incident.get("container") == "nginx"
        and incident.get("reason") in ("ImagePullBackOff", "ErrImagePull")
    ):
        recommendation = (
            "Test remediation proposal: update deployment/image-test "
            "container nginx from nginx:wrongtag12345 to nginx:latest. "
            "This action is restricted to this test deployment."
        )
    else:
        recommendation = (
            "Review the diagnostic evidence. No automatic remediation "
            "is configured for this incident."
        )

    return {
        "recommendation": recommendation,
        "status": "approval_pending"
    }


def human_approval_node(state):
    decision = interrupt({
        "message": "Review the AI analysis before proceeding.",
        "recommendation": state["recommendation"],
        "options": ["approve", "reject"]
    })

    decision = str(decision).strip().lower()

    if decision == "approve":
        return {
            "approval_decision": "approved",
            "status": "approved"
        }

    return {
        "approval_decision": "rejected",
        "status": "rejected"
    }


def remediation_node(state):
    incident = state.get("incident_context", {})

    # Strict test-only allowlist. All other incidents are blocked.
    if not (
        incident.get("namespace") == "default"
        and incident.get("pod", "").startswith("image-test-")
        and incident.get("container") == "nginx"
        and incident.get("reason") in ("ImagePullBackOff", "ErrImagePull")
    ):
        return {
            "remediation_result": {
                "status": "blocked",
                "message": "Incident is outside the approved test-only allowlist."
            },
            "status": "remediation_blocked"
        }

    try:
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()

        apps = client.AppsV1Api()
        namespace = "default"
        deployment_name = "image-test"
        container_name = "nginx"
        expected_image = "nginx:wrongtag12345"
        target_image = "nginx:latest"

        deployment = apps.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace
        )

        containers = deployment.spec.template.spec.containers
        target_container = next(
            (c for c in containers if c.name == container_name),
            None
        )

        if target_container is None:
            raise RuntimeError("Expected nginx container was not found.")

        if target_container.image != expected_image:
            raise RuntimeError(
                f"Image changed since diagnosis. Expected {expected_image}, "
                f"found {target_container.image}. Refusing to patch."
            )

        apps.patch_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
            body={
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [{
                                "name": container_name,
                                "image": target_image
                            }]
                        }
                    }
                }
            }
        )

        # Verify rollout for up to 120 seconds.
        deadline = time.time() + 120
        while time.time() < deadline:
            current = apps.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )
            desired = current.spec.replicas or 1
            status = current.status

            if (
                (status.updated_replicas or 0) >= desired
                and (status.available_replicas or 0) >= desired
                and (status.observed_generation or 0)
                    >= (current.metadata.generation or 0)
            ):
                return {
                    "remediation_result": {
                        "status": "success",
                        "deployment": deployment_name,
                        "namespace": namespace,
                        "container": container_name,
                        "old_image": expected_image,
                        "new_image": target_image,
                        "verification": "Deployment rollout successful"
                    },
                    "status": "remediation_completed"
                }

            time.sleep(5)

        raise TimeoutError("Deployment did not become available within 120 seconds.")

    except Exception as exc:
        return {
            "remediation_result": {
                "status": "failed",
                "message": str(exc),
                "note": "Check Deployment status before retrying."
            },
            "status": "remediation_failed"
        }


def route_after_diagnostics(state):
    return END if state.get("status") == "error" else "classification"


def route_after_classification(state):
    return END if state.get("classification") == "HEALTHY" else "ai_analysis"


def route_after_approval(state):
    if state.get("approval_decision") != "approved":
        return END

    if state.get("incident_context"):
        return "remediation"

    return END


def build_workflow(checkpointer):
    workflow = StateGraph(TroubleshootingState)

    workflow.add_node("diagnostics", diagnostic_node)
    workflow.add_node("classification", classification_node)
    workflow.add_node("ai_analysis", ai_analysis_node)
    workflow.add_node("recommendation", recommendation_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("remediation", remediation_node)

    workflow.add_edge(START, "diagnostics")
    workflow.add_conditional_edges("diagnostics", route_after_diagnostics)
    workflow.add_conditional_edges("classification", route_after_classification)
    workflow.add_edge("ai_analysis", "recommendation")
    workflow.add_edge("recommendation", "human_approval")
    workflow.add_conditional_edges("human_approval", route_after_approval)
    workflow.add_edge("remediation", END)

    return workflow.compile(checkpointer=checkpointer)
