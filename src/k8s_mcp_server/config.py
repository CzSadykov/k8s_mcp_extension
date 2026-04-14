"""Configuration helpers for the K8s MCP extension."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

LOG = logging.getLogger(__name__)

DEFAULT_TIMEOUT = int(os.getenv("K8S_MCP_TIMEOUT", "300"))
MAX_OUTPUT_SIZE = int(os.getenv("K8S_MCP_MAX_OUTPUT", "100000"))
K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "default")
KUBECONFIG_DIR = Path(os.getenv("K8S_KUBECONFIG_DIR", str(Path.home() / ".kube"))).expanduser()
MCP_TRANSPORT = os.getenv("K8S_MCP_TRANSPORT", "stdio")

SUPPORTED_CLI_TOOLS: dict[str, dict[str, str]] = {
    "kubectl": {
        "check_cmd": "kubectl version --client",
        "help_flag": "--help",
    },
    "istioctl": {
        "check_cmd": "istioctl version --remote=false",
        "help_flag": "--help",
    },
    "helm": {
        "check_cmd": "helm version",
        "help_flag": "--help",
    },
    "argocd": {
        "check_cmd": "argocd version --client",
        "help_flag": "--help",
    },
}

VALID_TRANSPORTS = {"stdio", "sse", "streamable-http"}


def default_node_prefix_mapping(username: str | None = None) -> dict[str, str]:
    """Return safe public defaults for node-prefix mapping."""

    _ = username
    return {}


def load_node_prefix_mapping(username: str | None = None) -> dict[str, str]:
    """Load node-prefix mapping from env and merge with defaults."""

    mapping = default_node_prefix_mapping(username=username)
    raw_mapping = os.getenv("K8S_NODE_PREFIX_MAPPING", "").strip()
    if not raw_mapping:
        return mapping

    try:
        loaded_mapping = json.loads(raw_mapping)
    except json.JSONDecodeError as error:
        raise ValueError("K8S_NODE_PREFIX_MAPPING must be a JSON object") from error

    if not isinstance(loaded_mapping, dict):
        raise ValueError("K8S_NODE_PREFIX_MAPPING must be a JSON object")

    normalized_mapping: dict[str, str] = {}
    for prefix, kubeconfig in loaded_mapping.items():
        if not isinstance(prefix, str) or not isinstance(kubeconfig, str):
            raise ValueError("K8S_NODE_PREFIX_MAPPING keys and values must be strings")
        normalized_mapping[prefix] = kubeconfig

    mapping.update(normalized_mapping)
    LOG.debug("Loaded %s node prefix mappings", len(mapping))
    return mapping


INSTRUCTIONS = """
K8s MCP Server for Kubernetes operations and node diagnostics.

Available node tools:
- run_checkup_on_node: switch kubeconfig by node prefix and run `checkup -n` via node-shell
- get_logs_on_node: collect node-level logs from dmesg, journalctl, /var/log, and /var/crash, then return a summary

Node routing is configured through K8S_NODE_PREFIX_MAPPING.
Provide a JSON object that maps a node prefix to a kubeconfig filename, for example:
{
  "node-a": "cluster-a.config",
  "edge": "edge-cluster.config"
}
"""
