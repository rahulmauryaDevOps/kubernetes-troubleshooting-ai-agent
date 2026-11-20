class DiagnosticEngine:

    def analyze(self, snapshot):
        findings = []
        seen = set()

        def add_finding(finding):
            key = (
                finding["namespace"],
                finding["pod"],
                finding["issue"],
                finding["evidence"]
            )

            if key not in seen:
                seen.add(key)
                findings.append(finding)

        pod_lookup = {}

        for pod in snapshot["pods"]:
            name = pod["name"]
            namespace = pod["namespace"]

            containers = pod["containers"]

            all_ready = (
                pod["phase"] == "Running"
                and bool(containers)
                and all(c["ready"] for c in containers)
            )

            pod_lookup[(namespace, name)] = {
                "healthy": all_ready,
                "phase": pod["phase"]
            }

            if pod["phase"] == "Pending":
                add_finding({
                    "namespace": namespace,
                    "pod": name,
                    "issue": "PodPending",
                    "severity": "WARNING",
                    "status": "ACTIVE",
                    "evidence": "Pod phase is Pending",
                    "recommendation": (
                        "Check node resources, taints, tolerations, "
                        "scheduling constraints and PVC binding."
                    )
                })

            for container in containers:
                waiting = container["waiting_reason"]
                last_terminated = container["last_terminated_reason"]

                if waiting == "CrashLoopBackOff":
                    add_finding({
                        "namespace": namespace,
                        "pod": name,
                        "issue": "CrashLoopBackOff",
                        "severity": "CRITICAL",
                        "status": "ACTIVE",
                        "evidence": (
                            f"Container {container['name']} "
                            "is in CrashLoopBackOff"
                        ),
                        "recommendation": (
                            "Inspect previous container logs, startup "
                            "configuration and application dependencies."
                        )
                    })

                elif waiting in ("ImagePullBackOff", "ErrImagePull"):
                    add_finding({
                        "namespace": namespace,
                        "pod": name,
                        "issue": "ImagePullBackOff",
                        "severity": "CRITICAL",
                        "status": "ACTIVE",
                        "evidence": (
                            f"Container {container['name']}: {waiting}"
                        ),
                        "recommendation": (
                            "Verify image name, tag, registry access "
                            "and image pull secrets."
                        )
                    })

                if last_terminated == "OOMKilled":
                    add_finding({
                        "namespace": namespace,
                        "pod": name,
                        "issue": "OOMKilled",
                        "severity": "CRITICAL",
                        "status": "HISTORICAL",
                        "evidence": (
                            f"Container {container['name']} was "
                            f"OOMKilled; exit code: "
                            f"{container['last_exit_code']}"
                        ),
                        "recommendation": (
                            "Review memory usage, memory limits "
                            "and possible memory leaks."
                        )
                    })

                if container["restart_count"] > 0:
                    add_finding({
                        "namespace": namespace,
                        "pod": name,
                        "issue": "ContainerRestart",
                        "severity": "WARNING",
                        "status": "ACTIVE" if not all_ready else "HISTORICAL",
                        "evidence": (
                            f"Container {container['name']} restarted "
                            f"{container['restart_count']} times."
                        ),
                        "recommendation": (
                            "Inspect current and previous container logs."
                        )
                    })

        # Correlate warning events with current pod health.
        for event in snapshot["events"]:
            if event["type"] != "Warning":
                continue

            if event.get("object_kind") != "Pod":
                continue

            key = (event["namespace"], event["object"])
            pod_info = pod_lookup.get(key)

            if pod_info is None:
                continue

            healthy = pod_info["healthy"]

            add_finding({
                "namespace": event["namespace"],
                "pod": event["object"],
                "issue": event["reason"] or "WarningEvent",
                "severity": "WARNING",
                "status": "HISTORICAL" if healthy else "ACTIVE",
                "evidence": event["message"],
                "last_seen": event.get("last_seen"),
                "recommendation": (
                    "Pod is currently healthy. Retain this warning "
                    "as historical evidence."
                    if healthy
                    else "Inspect pod events, scheduling and container "
                         "health to identify the current issue."
                )
            })

        return findings
