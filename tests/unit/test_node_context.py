"""Tests for node-to-context resolution."""

from k8s_mcp_server.node_context import NodeContextResolver


def test_resolves_context_for_known_prefix() -> None:
    resolver = NodeContextResolver(prefix_mapping={"node-a": "cluster-a.config"})

    context = resolver.resolve_context("node-a-worker-01")

    assert context == "cluster-a.config"


def test_returns_static_context_for_known_prefix() -> None:
    resolver = NodeContextResolver(
        prefix_mapping={
            "node-a": "cluster-a.config",
            "edge": "edge-cluster.config",
        },
    )

    context = resolver.resolve_context("edge-worker-17")

    assert context == "edge-cluster.config"


def test_matches_prefix_case_insensitively() -> None:
    resolver = NodeContextResolver(prefix_mapping={"node-a": "cluster-a.config"})

    context = resolver.resolve_context("NODE-A-worker-01")

    assert context == "cluster-a.config"


def test_raises_for_unknown_node_prefix() -> None:
    resolver = NodeContextResolver(prefix_mapping={})

    try:
        resolver.resolve_context("unknown-node-01")
    except ValueError as error:
        assert "K8S_NODE_PREFIX_MAPPING" in str(error)
        assert "unknown-node-01" in str(error)
    else:
        raise AssertionError("Expected ValueError for an unknown node prefix")
