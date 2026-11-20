from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException


def load_config():
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()


def cpu_millicores(value):
    value = str(value)
    if value.endswith("n"):
        return float(value[:-1]) / 1_000_000
    if value.endswith("u"):
        return float(value[:-1]) / 1000
    if value.endswith("m"):
        return float(value[:-1])
    return float(value) * 1000


def memory_mib(value):
    value = str(value)
    units = {
        "Ki": 1 / 1024,
        "Mi": 1,
        "Gi": 1024,
        "Ti": 1024 * 1024,
        "K": 1 / 1024,
        "M": 1,
        "G": 1024,
    }

    for unit, factor in units.items():
        if value.endswith(unit):
            return float(value[:-len(unit)]) * factor

    return int(value) / (1024 * 1024)


def get_cluster_health():
    load_config()

    core = client.CoreV1Api()
    custom = client.CustomObjectsApi()

    nodes = core.list_node().items
    pods = core.list_pod_for_all_namespaces().items

    ready_nodes = 0
    node_details = []
    capacities = {}

    for node in nodes:
        conditions = {
            c.type: c.status
            for c in (node.status.conditions or [])
        }

        ready = conditions.get("Ready") == "True"
        ready_nodes += int(ready)

        allocatable = node.status.allocatable or {}
        capacities[node.metadata.name] = {
            "cpu": cpu_millicores(allocatable.get("cpu", "0")),
            "memory": memory_mib(allocatable.get("memory", "0"))
        }

        node_details.append({
            "name": node.metadata.name,
            "status": "Ready" if ready else "NotReady",
            "cpu_capacity": node.status.capacity.get("cpu"),
            "memory_capacity": node.status.capacity.get("memory"),
            "cpu_allocatable": allocatable.get("cpu"),
            "memory_allocatable": allocatable.get("memory"),
        })

    pod_counts = {
        "Running": 0,
        "Pending": 0,
        "Failed": 0,
        "Succeeded": 0,
        "Unknown": 0,
    }

    for pod in pods:
        phase = pod.status.phase or "Unknown"
        pod_counts[phase] = pod_counts.get(phase, 0) + 1

    result = {
        "total_nodes": len(nodes),
        "ready_nodes": ready_nodes,
        "not_ready_nodes": len(nodes) - ready_nodes,
        "total_pods": len(pods),
        "pod_counts": pod_counts,
        "nodes": node_details,
        "metrics_available": False,
        "node_metrics": [],
    }

    try:
        metrics = custom.list_cluster_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            plural="nodes"
        )

        for item in metrics.get("items", []):
            name = item["metadata"]["name"]
            usage = item.get("usage", {})
            cpu_used = cpu_millicores(usage["cpu"])
            memory_used = memory_mib(usage["memory"])
            capacity = capacities.get(name, {})

            cpu_total = capacity.get("cpu", 0)
            memory_total = capacity.get("memory", 0)

            result["node_metrics"].append({
                "name": name,
                "cpu_usage_millicores": round(cpu_used, 2),
                "cpu_usage_percent": round(
                    cpu_used / cpu_total * 100, 2
                ) if cpu_total else 0,
                "memory_usage_mib": round(memory_used, 2),
                "memory_usage_percent": round(
                    memory_used / memory_total * 100, 2
                ) if memory_total else 0,
            })

        result["metrics_available"] = True

    except Exception as exc:
        result["metrics_error"] = str(exc)

    return result
