"""Tests for public-safe configuration defaults."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import k8s_mcp_server.config as config_module


def reload_config():
    """Reload the configuration module after environment changes."""

    return importlib.reload(config_module)


def test_default_node_prefix_mapping_is_empty() -> None:
    config = reload_config()

    assert config.default_node_prefix_mapping() == {}


def test_load_node_prefix_mapping_uses_environment_only(monkeypatch: pytest.MonkeyPatch) -> None:
    config = reload_config()
    monkeypatch.setenv(
        "K8S_NODE_PREFIX_MAPPING",
        '{"node-a": "cluster-a.config", "node-b": "cluster-b.config"}',
    )

    mapping = config.load_node_prefix_mapping()

    assert mapping == {
        "node-a": "cluster-a.config",
        "node-b": "cluster-b.config",
    }


def test_default_kubeconfig_dir_uses_standard_kube_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("K8S_KUBECONFIG_DIR", raising=False)

    config = reload_config()

    assert config.KUBECONFIG_DIR == (Path.home() / ".kube").expanduser()
