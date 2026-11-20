from app.collectors.kubernetes_collector import KubernetesCollector
from app.analyzers.diagnostic_engine import DiagnosticEngine

collector = KubernetesCollector()
snapshot = collector.get_cluster_snapshot()

engine = DiagnosticEngine()
findings = engine.analyze(snapshot)

active = [f for f in findings if f["status"] == "ACTIVE"]
historical = [f for f in findings if f["status"] == "HISTORICAL"]

print("\n========== CLUSTER DIAGNOSTICS ==========")

for finding in findings:
    print(f"\n[{finding['status']}] {finding['issue']}")
    print("Severity:", finding["severity"])
    print("Namespace:", finding["namespace"])
    print("Pod:", finding["pod"])
    print("Evidence:", finding["evidence"])
    print("Recommendation:", finding["recommendation"])

print("\n========== SUMMARY ==========")
print("Total findings:", len(findings))
print("Active findings:", len(active))
print("Historical findings:", len(historical))
