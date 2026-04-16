"""Node-to-kubeconfig resolution.

This module provides functionality to map Kubernetes node names to appropriate
kubeconfig files based on node naming conventions. The primary use case is to
route requests to the correct Kubernetes cluster based on the node name structure.
"""

from __future__ import annotations

from dataclasses import dataclass

from k8s_mcp_server.config import load_node_prefix_mapping


@dataclass(frozen=True)
class NodeContextResolver:
    """Resolve a kubeconfig name from a node name.

    This resolver uses a mapping dictionary to determine which kubeconfig file
    should be used for a given node name. The mapping can be based on:
    1. Second segment of the node name (split by dots) - primary method
    2. Substring matching - fallback method for backward compatibility
    """

    # Dictionary mapping node identifiers to kubeconfig filenames
    prefix_mapping: dict[str, str]

    @classmethod
    def default(cls, username: str | None = None) -> NodeContextResolver:
        """Create a resolver instance with the default configuration.

        Loads the node prefix mapping from environment variables and defaults.

        Args:
            username: Optional username for user-specific configurations

        Returns:
            NodeContextResolver: A configured resolver instance
        """
        return cls(prefix_mapping=load_node_prefix_mapping(username=username))

    def resolve_context(self, node_name: str) -> str:
        """Resolve kubeconfig filename for a node based on naming conventions.

        This method implements a two-tier resolution strategy:
        1. Primary: Extract the second segment from the node name (split by dots)
           and match it against the prefix mapping. For example, for a node named
           'reg01-srv-001.cluster01.example.local', the second segment 'cluster01'
           would be used to look up the corresponding kubeconfig.

        2. Fallback: If no match is found in the primary method, fall back to
           substring matching for backward compatibility with older naming schemes.

        Args:
            node_name: The full name of the Kubernetes node

        Returns:
            str: The kubeconfig filename that should be used for this node

        Raises:
            ValueError: If no kubeconfig can be resolved for the given node name
        """
        # Normalize the node name for consistent processing
        normalized_name = node_name.strip().lower()

        # Extract segments from node name (split by dots)
        # For example: 'reg01-srv-001.cluster01.example.local' -> ['reg01-srv-001', 'cluster01', 'example', 'local']
        segments = normalized_name.split('.')

        # Use the second segment as the cluster identifier (if available)
        # This is the primary resolution method for modern node naming conventions
        if len(segments) >= 2:
            second_segment = segments[1]

            # Check if we have a mapping for this segment
            if second_segment in self.prefix_mapping:
                return self.prefix_mapping[second_segment]

        # Fallback to substring matching for backward compatibility
        # This maintains compatibility with older node naming schemes
        ordered_substrings = sorted(self.prefix_mapping.keys(), key=len, reverse=True)
        for substring in ordered_substrings:
            if substring.lower() in normalized_name:
                return self.prefix_mapping[substring]

        # If no mapping is found, raise an error with guidance for configuration
        raise ValueError(
            f"Unable to resolve kubeconfig for node '{node_name}'. "
            "Configure K8S_NODE_PREFIX_MAPPING with a JSON object that maps node identifiers to kubeconfig filenames.",
        )
