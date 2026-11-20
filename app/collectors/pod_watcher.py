import logging
import threading
from kubernetes import client, config, watch
from kubernetes.config.config_exception import ConfigException

logger = logging.getLogger(__name__)

ERROR_REASONS = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerConfigError",
    "CreateContainerError",
    "RunContainerError",
}


class PodWatcher:
    def __init__(self, on_incident):
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()

        self.core_v1 = client.CoreV1Api()
        self.on_incident = on_incident
        self.stop_event = threading.Event()
        self.thread = None

        # Identity excludes error reason to prevent duplicate incidents.
        self.reported = set()

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._watch_pods,
            daemon=True,
            name="kubernetes-pod-watcher",
        )
        self.thread.start()
        logger.info("Kubernetes Pod watcher started")

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)

    def _watch_pods(self):
        while not self.stop_event.is_set():
            stream = watch.Watch()

            try:
                for event in stream.stream(
                    self.core_v1.list_pod_for_all_namespaces,
                    timeout_seconds=30,
                ):
                    if self.stop_event.is_set():
                        break

                    if event["type"] == "DELETED":
                        continue

                    pod = event["object"]
                    namespace = pod.metadata.namespace
                    pod_name = pod.metadata.name

                    statuses = pod.status.container_statuses or []
                    active_error_keys = set()

                    for status in statuses:
                        key = (namespace, pod_name, status.name)
                        waiting = status.state.waiting

                        if waiting and waiting.reason in ERROR_REASONS:
                            active_error_keys.add(key)

                            if key in self.reported:
                                continue

                            self.reported.add(key)

                            incident = {
                                "namespace": namespace,
                                "pod": pod_name,
                                "container": status.name,
                                "reason": waiting.reason,
                                "message": waiting.message,
                                "detected_by": "Kubernetes Watch API",
                            }

                            logger.warning(
                                "Pod incident detected: %s", incident
                            )

                            try:
                                self.on_incident(incident)
                            except Exception:
                                logger.exception(
                                    "Incident callback failed"
                                )

                    # Clear deduplication when the container recovers.
                    self.reported = {
                        key for key in self.reported
                        if not (
                            key[0] == namespace
                            and key[1] == pod_name
                            and key not in active_error_keys
                        )
                    }

            except Exception:
                logger.exception("Pod watcher error; retrying")

            finally:
                stream.stop()

            self.stop_event.wait(5)
