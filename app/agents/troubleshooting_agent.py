import json

from app.agents.k8sgpt_engine import run_k8sgpt_analysis
from app.agents.groq_engine import explain_findings


def run_troubleshooting_agent():
    print("Starting Kubernetes Troubleshooting Agent...")

    # Step 1: Collect Kubernetes findings
    diagnostic_result = run_k8sgpt_analysis()

    if diagnostic_result["status"] != "success":
        return diagnostic_result

    findings = diagnostic_result["findings"]

    # Step 2: Send findings to Groq
    print("Sending findings to Groq AI...")

    explanation = explain_findings(findings)

    return {
        "status": "success",
        "total_problems": findings.get("problems", 0),
        "diagnostics": findings,
        "ai_explanation": explanation
    }


if __name__ == "__main__":
    result = run_troubleshooting_agent()
    print(json.dumps(result, indent=4))
