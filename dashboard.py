import streamlit as st
import requests
import pandas as pd
from datetime import datetime

API = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Kubernetes AI Operations",
    page_icon="☸️",
    layout="wide"
)

st.title("☸️ Kubernetes AI Operations Center")
st.caption("Live EKS cluster health, resource monitoring and AI remediation")

if st.button("🔄 Refresh Dashboard"):
    st.rerun()

try:
    requests.get(f"{API}/health", timeout=5).raise_for_status()
    incidents_response = requests.get(f"{API}/incidents", timeout=10)
    incidents_response.raise_for_status()
    incidents = incidents_response.json().get("incidents", [])

    health_response = requests.get(f"{API}/cluster-health", timeout=20)
    health_response.raise_for_status()
    cluster = health_response.json()

    st.success("Backend and Kubernetes cluster connected")

except requests.RequestException as exc:
    st.error(f"Backend or Kubernetes API error: {exc}")
    st.stop()

st.header("Cluster Overview")

a, b, c, d = st.columns(4)
a.metric("Total Nodes", cluster["total_nodes"])
b.metric("Ready Nodes", cluster["ready_nodes"])
c.metric("Total Pods", cluster["total_pods"])
d.metric("Not Ready Nodes", cluster["not_ready_nodes"])

st.subheader("Pod Status")

a, b, c, d, e = st.columns(5)
counts = cluster["pod_counts"]
a.metric("Running", counts.get("Running", 0))
b.metric("Pending", counts.get("Pending", 0))
c.metric("Failed", counts.get("Failed", 0))
d.metric("Succeeded", counts.get("Succeeded", 0))
e.metric("Unknown", counts.get("Unknown", 0))

st.subheader("Node Health")
st.dataframe(cluster["nodes"], use_container_width=True, hide_index=True)

st.subheader("Node Resource Utilization")

if cluster["metrics_available"] and cluster["node_metrics"]:
    metrics_df = pd.DataFrame(cluster["node_metrics"])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**CPU Utilization (%)**")
        st.bar_chart(
            metrics_df.set_index("name")["cpu_usage_percent"],
            y_label="CPU Usage %",
        )

    with col2:
        st.markdown("**Memory Utilization (%)**")
        st.bar_chart(
            metrics_df.set_index("name")["memory_usage_percent"],
            y_label="Memory Usage %",
        )

    st.markdown("**Detailed Node Metrics**")
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)

else:
    st.warning("Node metrics are unavailable. Check metrics-server.")

st.divider()
st.header("AI Incident Management")

total = len(incidents)
pending = sum(i.get("status") == "awaiting_human_review" for i in incidents)
successful = sum(
    i.get("remediation_result", {}).get("status") == "success"
    for i in incidents
)
failed = sum(
    i.get("remediation_result", {}).get("status") == "failed"
    for i in incidents
)

a, b, c, d = st.columns(4)
a.metric("Total Incidents", total)
b.metric("Awaiting Approval", pending)
c.metric("Successful Fixes", successful)
d.metric("Failed Fixes", failed)

if not incidents:
    st.info("No incidents detected yet.")

for index, incident in enumerate(reversed(incidents)):
    details = incident.get("incident", {})
    status = incident.get("status", "unknown")
    thread_id = incident.get("thread_id", "")

    with st.expander(
        f"{details.get('reason', 'Unknown')} | "
        f"{details.get('pod', 'Unknown Pod')} | {status}",
        expanded=(index == 0)
    ):
        st.write("**Namespace:**", details.get("namespace"))
        st.write("**Pod:**", details.get("pod"))
        st.write("**Container:**", details.get("container"))
        st.write("**Error:**", details.get("message"))

        st.markdown("### AI Root Cause Analysis")
        st.write(incident.get("ai_explanation", "Not available"))

        st.markdown("### Recommended Action")
        st.write(incident.get("recommendation", "Not available"))

        if incident.get("remediation_result"):
            st.markdown("### Remediation Result")
            st.json(incident["remediation_result"])

        if status == "awaiting_human_review":
            st.warning("Human approval required.")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("✅ Approve Fix", key=f"approve_{thread_id}"):
                    try:
                        response = requests.post(
                            f"{API}/approve/{thread_id}",
                            json={"decision": "approve"},
                            timeout=150
                        )
                        response.raise_for_status()
                        st.success("Approval processed")
                        st.json(response.json())
                        st.rerun()
                    except requests.RequestException as exc:
                        st.error(str(exc))

            with col2:
                if st.button("❌ Reject Fix", key=f"reject_{thread_id}"):
                    try:
                        response = requests.post(
                            f"{API}/approve/{thread_id}",
                            json={"decision": "reject"},
                            timeout=30
                        )
                        response.raise_for_status()
                        st.success("Recommendation rejected")
                        st.rerun()
                    except requests.RequestException as exc:
                        st.error(str(exc))

st.divider()
st.caption(
    "Kubernetes AI Operations Center | Refreshed: "
    + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)
