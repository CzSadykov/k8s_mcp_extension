"""Cluster-aware node information service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from k8s_mcp_server.config import KUBECONFIG_DIR
from k8s_mcp_server.node_context import NodeContextResolver

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class KubernetesNodeService:
    """Read node information from the target cluster using the Kubernetes Python client."""

    context_resolver: NodeContextResolver
    kubeconfig_dir: str | Path = KUBECONFIG_DIR

    def get_node_status(self, node_name: str) -> dict[str, object]:
        """Return high-level node status and conditions."""

        core_api, kubeconfig_path = self._core_api(node_name)
        node = core_api.read_node(node_name)
        conditions = node.status.conditions if node.status and node.status.conditions else []
        ready_status = next((condition.status for condition in conditions if condition.type == "Ready"), "Unknown")
        return {
            "name": node.metadata.name,
            "cluster_kubeconfig": kubeconfig_path.name,
            "roles": node.metadata.labels.get("kubernetes.io/role", "worker"),
            "os_image": getattr(node.status.node_info, "os_image", "unknown"),
            "kubelet_version": getattr(node.status.node_info, "kubelet_version", "unknown"),
            "conditions": [
                {
                    "type": condition.type,
                    "status": condition.status,
                    "reason": condition.reason,
                    "message": condition.message,
                }
                for condition in conditions
            ],
            "overall_status": "Ready" if ready_status == "True" else "NotReady",
        }

    def get_node_labels(self, node_name: str) -> dict[str, object]:
        """Return node labels."""

        core_api, _ = self._core_api(node_name)
        node = core_api.read_node(node_name)
        labels = dict(node.metadata.labels or {})
        return {
            "node_name": node_name,
            "labels": labels,
            "count": len(labels),
        }

    def get_pods_on_node(self, node_name: str) -> dict[str, object]:
        """Return pods scheduled onto a specific node."""

        core_api, _ = self._core_api(node_name)
        pods = core_api.list_pod_for_all_namespaces(
            watch=False,
            field_selector=f"spec.nodeName={node_name}",
        )

        pod_list: list[dict[str, object]] = []
        for pod in pods.items:
            restarts = 0
            if pod.status and pod.status.container_statuses:
                restarts = sum(container.restart_count for container in pod.status.container_statuses)

            pod_info: dict[str, object] = {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "phase": pod.status.phase if pod.status else "Unknown",
                "restarts": restarts,
                "created": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else "Unknown",
            }
            if pod.status and pod.status.container_statuses:
                pod_info["containers"] = [
                    {
                        "name": container.name,
                        "ready": container.ready,
                        "restart_count": container.restart_count,
                        "state": str(container.state) if container.state else "Unknown",
                    }
                    for container in pod.status.container_statuses
                ]
            pod_list.append(pod_info)

        pods_by_namespace: dict[str, list[dict[str, object]]] = {}
        for pod_info in pod_list:
            namespace = str(pod_info["namespace"])
            pods_by_namespace.setdefault(namespace, []).append(pod_info)

        return {
            "node_name": node_name,
            "total_pods": len(pod_list),
            "pods_by_namespace": pods_by_namespace,
            "all_pods": pod_list,
        }

    def get_node_resources(self, node_name: str) -> dict[str, object]:
        """Return allocatable and current pod usage for a node."""

        core_api, _ = self._core_api(node_name)
        node = core_api.read_node(node_name)
        capacity = node.status.capacity if node.status.capacity else {}
        allocatable = node.status.allocatable if node.status.allocatable else {}
        pods = core_api.list_pod_for_all_namespaces(
            watch=False,
            field_selector=f"spec.nodeName={node_name}",
        )
        running_pods = len([pod for pod in pods.items if pod.status and pod.status.phase == "Running"])
        return {
            "node_name": node_name,
            "capacity": {
                "cpu": capacity.get("cpu", "N/A"),
                "memory": capacity.get("memory", "N/A"),
                "pods": capacity.get("pods", "N/A"),
            },
            "allocatable": {
                "cpu": allocatable.get("cpu", "N/A"),
                "memory": allocatable.get("memory", "N/A"),
                "pods": allocatable.get("pods", "N/A"),
            },
            "current_usage": {
                "running_pods": running_pods,
                "total_pods": len(pods.items),
            },
        }

    def _core_api(self, node_name: str):
        kubeconfig_path = self._resolve_kubeconfig_path(node_name)
        kubernetes = self._load_kubernetes_module()
        client = kubernetes.config.new_client_from_config(config_file=str(kubeconfig_path))
        return kubernetes.client.CoreV1Api(client), kubeconfig_path

    def _resolve_kubeconfig_path(self, node_name: str) -> Path:
        kubeconfig_name = self.context_resolver.resolve_context(node_name)
        kubeconfig_path = Path(self.kubeconfig_dir).expanduser() / kubeconfig_name
        if not kubeconfig_path.is_file():
            raise FileNotFoundError(f"Kubeconfig file was not found: {kubeconfig_path}")
        return kubeconfig_path

    @staticmethod
    def _load_kubernetes_module():
        try:
            import kubernetes
        except ModuleNotFoundError as error:
            raise RuntimeError("Install the `kubernetes` package to use node information tools") from error
        return kubernetes
