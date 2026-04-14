"""Node-to-kubeconfig resolution."""

from __future__ import annotations

from dataclasses import dataclass

from k8s_mcp_server.config import load_node_prefix_mapping


@dataclass(frozen=True)
class NodeContextResolver:
    """Resolve a kubeconfig name from a node name."""

    prefix_mapping: dict[str, str]

    @classmethod
    def default(cls, username: str | None = None) -> NodeContextResolver:
        """Create a resolver from configured defaults."""

        return cls(prefix_mapping=load_node_prefix_mapping(username=username))

    def resolve_context(self, node_name: str) -> str:
        """Resolve kubeconfig filename for a node."""

        normalized_name = node_name.strip().lower()
        ordered_prefixes = sorted(self.prefix_mapping, key=len, reverse=True)
        for prefix in ordered_prefixes:
            if normalized_name.startswith(prefix.lower()):
                return self.prefix_mapping[prefix]
        raise ValueError(
            f"Unable to resolve kubeconfig for node '{node_name}'. "
            "Configure K8S_NODE_PREFIX_MAPPING with a JSON object that maps node prefixes to kubeconfig filenames.",
        )
