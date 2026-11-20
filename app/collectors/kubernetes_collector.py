from kubernetes import client, config


class KubernetesCollector:
    def __init__(self):
        config.load_kube_config()
        self.core_v1 = client.CoreV1Api()

    def get_nodes(self):
        nodes = self.core_v1.list_node().items
        result = []

        for node in nodes:
            conditions = {
                c.type: c.status
                for c in (node.status.conditions or [])
            }

            result.append({
                "name": node.metadata.name,
                "status": conditions.get("Ready", "Unknown"),
                "internal_ip": next(
                    (a.address for a in node.status.addresses
                     if a.type == "InternalIP"), None
                )
            })

        return result

    def get_pods(self):
        pods = self.core_v1.list_pod_for_all_namespaces().items
        result = []

        for pod in pods:
            containers = []

            for status in pod.status.container_statuses or []:
                waiting = status.state.waiting
                terminated = status.state.terminated
                last_terminated = status.last_state.terminated

                containers.append({
                    "name": status.name,
                    "ready": status.ready,
                    "restart_count": status.restart_count,
                    "waiting_reason": waiting.reason if waiting else None,
                    "waiting_message": waiting.message if waiting else None,
                    "terminated_reason": (
                        terminated.reason if terminated else None
                    ),
                    "last_terminated_reason": (
                        last_terminated.reason if last_terminated else None
                    ),
                    "last_exit_code": (
                        last_terminated.exit_code if last_terminated else None
                    )
                })

            result.append({
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "phase": pod.status.phase,
                "node": pod.spec.node_name,
                "restart_count": sum(c["restart_count"] for c in containers),
                "containers": containers
            })

        return result

    def get_events(self):
        events = self.core_v1.list_event_for_all_namespaces().items

        return [{
            "namespace": e.metadata.namespace,
            "type": e.type,
            "reason": e.reason,
            "object": e.involved_object.name,
            "object_kind": e.involved_object.kind,
            "message": e.message,
            "count": e.count,
            "last_seen": (
                e.last_timestamp.isoformat()
                if e.last_timestamp
                else (
                    e.event_time.isoformat()
                    if e.event_time
                    else (
                        e.metadata.creation_timestamp.isoformat()
                        if e.metadata.creation_timestamp
                        else None
                    )
                )
            )
        } for e in events]

    def get_cluster_snapshot(self):
        return {
            "nodes": self.get_nodes(),
            "pods": self.get_pods(),
            "events": self.get_events()
        }


if __name__ == "__main__":
    collector = KubernetesCollector()
    snapshot = collector.get_cluster_snapshot()

    print("Nodes:", len(snapshot["nodes"]))
    print("Pods:", len(snapshot["pods"]))
    print("Events:", len(snapshot["events"]))
    print("\nPod details:")

    for pod in snapshot["pods"]:
        print(pod)
