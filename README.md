# 🚀 Kubernetes Troubleshooting AI Agent

An AI-powered Kubernetes troubleshooting and incident remediation platform built on **AWS EKS**. It continuously monitors Kubernetes workloads, detects application issues, analyzes root causes using AI, recommends corrective actions, and performs controlled remediation after human approval.

The platform combines Kubernetes monitoring, Groq AI, LangGraph, FastAPI, Streamlit, and Slack notifications to simplify Kubernetes incident management.

---

## 📌 Project Overview

Managing Kubernetes production environments requires continuous monitoring, quick incident detection, root cause analysis, and safe remediation.

This project aims to automate parts of that operational workflow using an AI-powered troubleshooting agent.

The agent detects Kubernetes pod failures, collects diagnostic information, uses AI to explain the problem, and presents remediation recommendations for human approval.

Once approved, the agent executes an allowlisted remediation action and verifies the Kubernetes deployment rollout.

## 🎯 Key Features

- **Real-Time Incident Detection:** Monitors Kubernetes pod events and detects container failures.
- **AI-Powered Root Cause Analysis:** Uses Groq LLM to analyze incidents and explain their impact.
- **Kubernetes Diagnostics:** Collects pod, node, and event information.
- **K8sGPT Integration:** Uses K8sGPT for Kubernetes diagnostic analysis.
- **LangGraph Workflow:** Orchestrates the troubleshooting and remediation lifecycle.
- **Human-in-the-Loop Approval:** Requires human approval before executing remediation.
- **Controlled Auto-Remediation:** Executes only explicitly allowlisted remediation actions.
- **Slack Notifications:** Sends incident, AI analysis, approval, and remediation notifications.
- **FastAPI Backend:** Exposes REST APIs for troubleshooting and incident management.
- **Streamlit Dashboard:** Provides a web interface for cluster health, incident analysis, and approval.
- **SQLite Checkpointing:** Uses SQLite to maintain LangGraph workflow checkpoints.

## 🏗️ Architecture

```text
                  Kubernetes Cluster
                     (AWS EKS)
                          |
                          |
                  Kubernetes Watcher
                          |
                          v
                 Incident Detection
                          |
                          v
               Kubernetes Diagnostics
                          |
                          v
                    K8sGPT
                          |
                          v
                  LangGraph Workflow
                          |
                +---------+---------+
                |                   |
                v                   v
          Incident Analysis     Groq LLM
                |                   |
                +---------+---------+
                          |
                          v
                 Root Cause Analysis
                          |
                          v
                 Remediation Proposal
                          |
                          v
                  Human Approval
                          |
                    +-----+-----+
                    |           |
                  Reject      Approve
                    |           |
                    v           v
                   End     Remediation Agent
                                |
                                v
                       Kubernetes API
                                |
                                v
                       Rollout Verification
                                |
                                v
                        Slack Notification

        FastAPI Backend  <---->  Streamlit Dashboard
```

## 🛠️ Technology Stack

| Category | Technologies |
|---|---|
| Cloud Platform | AWS |
| Kubernetes | Amazon EKS |
| Containerization | Docker |
| Programming Language | Python |
| AI / LLM | Groq |
| AI Workflow | LangGraph |
| Kubernetes Diagnostics | K8sGPT |
| Backend | FastAPI |
| Frontend Dashboard | Streamlit |
| Kubernetes SDK | Kubernetes Python Client |
| Database / Checkpointing | SQLite |
| Notifications | Slack Incoming Webhooks |
| Infrastructure | AWS EC2, EKS |

## 🔄 How It Works

### 1. Kubernetes Monitoring

The Kubernetes watcher continuously monitors pod events across namespaces.

It identifies common container failure conditions, including:

- CrashLoopBackOff
- ImagePullBackOff
- ErrImagePull
- CreateContainerConfigError
- CreateContainerError
- RunContainerError

### 2. Incident Detection

When a failure is detected, the agent collects incident details such as:

- Namespace
- Pod name
- Container name
- Failure reason
- Error message

Duplicate incidents are controlled using an incident deduplication mechanism.

### 3. AI-Powered Analysis

The diagnostic information is passed into the LangGraph workflow.

Groq AI analyzes the issue and provides:

- Root cause
- Potential impact
- Troubleshooting checks
- Recommended corrective action

### 4. Human Approval

Before performing any remediation, the workflow pauses for human approval.

The operator can review the recommendation through the Streamlit dashboard.

### 5. Controlled Remediation

After approval, the remediation agent checks whether the requested action matches its allowlist.

For the implemented ImagePullBackOff test scenario, it updates the test deployment image from:

`nginx:wrongtag12345`

to:

`nginx:latest`

The agent does not automatically modify arbitrary production workloads.

### 6. Rollout Verification

After applying the change, the agent checks the Kubernetes deployment rollout and verifies whether the expected replicas become available.

### 7. Slack Notifications

Slack receives notifications for:

- Incident detected
- AI analysis completed
- Approval pending
- Remediation successful
- Remediation failed

---

## 📂 Project Structure

```text
k8s-troubleshooting-ai-agent/
│
├── app/
│   ├── agents/
│   │   ├── groq_engine.py
│   │   ├── k8sgpt_engine.py
│   │   ├── langgraph_workflow.py
│   │   ├── troubleshooting_agent.py
│   │   └── slack_notifier.py
│   │
│   ├── analyzers/
│   │   └── diagnostic_engine.py
│   │
│   ├── collectors/
│   │   ├── cluster_health.py
│   │   ├── kubernetes_collector.py
│   │   └── pod_watcher.py
│   │
│   └── main.py
│
├── dashboard.py
├── requirements.txt
├── .gitignore
└── README.md
```

## ⚙️ Deployment Environment

The project was deployed and tested using:

- AWS EC2 Ubuntu instance as the application host.
- Amazon EKS as the Kubernetes environment.
- Kubernetes Python Client for cluster communication.
- IAM role attached to the EC2 instance for AWS access.
- Groq API for AI-powered incident analysis.
- Slack Incoming Webhook for notifications.

## 🚀 Installation & Setup

### Prerequisites

- AWS account
- Running Amazon EKS cluster
- Ubuntu EC2 instance
- Python 3
- kubectl
- K8sGPT CLI
- Groq API key
- Slack Incoming Webhook URL

### 1. Clone Repository

```bash
git clone https://github.com/rahulmauryaDevOps/kubernetes-troubleshooting-ai-agent.git

cd kubernetes-troubleshooting-ai-agent
```

### 2. Create Python Virtual Environment

```bash
python3 -m venv venv

source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
SLACK_WEBHOOK_URL=your_slack_webhook_url
```

Never commit `.env` or expose API keys and webhook URLs in GitHub.

### 5. Configure Kubernetes Access

For an EC2 instance with the appropriate IAM role:

```bash
aws eks update-kubeconfig \
  --region us-east-2 \
  --name k8s-ai-agent-dev
```

Verify connectivity:

```bash
kubectl get nodes
kubectl get pods -A
```

### 6. Start FastAPI Backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 7. Start Streamlit Dashboard

Open another terminal:

```bash
cd k8s-troubleshooting-ai-agent

source venv/bin/activate

streamlit run dashboard.py \
  --server.address 0.0.0.0 \
  --server.port 8501
```

## 🌐 Application Access

| Component | URL |
|---|---|
| FastAPI Backend | `http://EC2_PUBLIC_IP:8000` |
| Swagger API Documentation | `http://EC2_PUBLIC_IP:8000/docs` |
| Streamlit Dashboard | `http://EC2_PUBLIC_IP:8501` |

Restrict inbound access to trusted IP addresses. Do not expose application ports publicly without appropriate security controls.

## 🔌 API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Application information |
| GET | `/health` | Application health check |
| GET | `/incidents` | Retrieve detected incidents |
| POST | `/troubleshoot` | Trigger troubleshooting |
| POST | `/approve/{thread_id}` | Approve or reject remediation |
| GET | `/cluster-health` | Retrieve cluster health information |

## 🧪 Tested Scenario: ImagePullBackOff

A Kubernetes deployment was intentionally created with an invalid container image.

```bash
kubectl create deployment image-test \
  --image=nginx:wrongtag12345
```

### Initial Problem

The pod entered an `ErrImagePull` / `ImagePullBackOff` state because the requested image tag was unavailable.

### Agent Workflow

1. Kubernetes watcher detected the incident.
2. Slack received an incident notification.
3. Groq AI analyzed the failure.
4. The agent generated a remediation recommendation.
5. Human approval was requested through the dashboard.
6. After approval, the agent updated the deployment image.
7. Kubernetes rollout was verified.
8. Slack received the remediation success notification.

### Verification

```bash
kubectl get deployments
kubectl get pods
```

Expected result:

- Deployment: `image-test`
- Desired replicas: 1
- Available replicas: 1
- Pod status: Running
- Container image: `nginx:latest`

**Result:** End-to-end incident detection, AI analysis, human approval, remediation, rollout verification, and Slack notification successfully tested.

## 🔐 Security & Safety

The project follows a controlled remediation approach:

- Human approval is required before remediation.
- Remediation actions are restricted through an allowlist.
- Kubernetes access is provided through AWS IAM-based access.
- API keys and Slack webhook URLs are stored in environment variables.
- Secrets and local runtime files are excluded through `.gitignore`.
- Arbitrary production workload modifications are not enabled.

## ⚠️ Current Limitations

- Automated remediation currently supports a specific allowlisted ImagePullBackOff test scenario.
- Generic production workload remediation is not enabled.
- Incident history is currently maintained in application memory and is not yet persisted in a dedicated incident database.
- Slack is currently used for notifications; approval is handled through the dashboard.

## 🔮 Future Enhancements

- Persistent incident management using PostgreSQL.
- More Kubernetes failure scenarios and diagnostic rules.
- Configurable remediation policies.
- Role-based approval and access control.
- Slack-based interactive approval.
- Prometheus and Grafana integration.
- Audit logs and remediation history.
- Production-grade authentication and authorization.
- Improved incident deduplication and workflow resilience.

## 👨‍💻 Author

**Rahul Maurya**

Senior DevOps Engineer

GitHub: [@rahulmauryaDevOps](https://github.com/rahulmauryaDevOps)

---

## ⭐ Support

If you find this project useful, consider giving the repository a ⭐ on GitHub.

**Built to make Kubernetes troubleshooting smarter, safer, and faster with AI.**
