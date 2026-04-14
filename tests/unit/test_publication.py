"""Tests for publication-facing project metadata."""

from __future__ import annotations

import tomllib
from pathlib import Path


def _project_metadata() -> dict[str, object]:
    with Path("pyproject.toml").open("rb") as file:
        return tomllib.load(file)["project"]


def test_distribution_metadata_is_present() -> None:
    project = _project_metadata()

    assert project["scripts"] == {
        "k8s-mcp-server": "k8s_mcp_server.__main__:main",
    }
    assert "classifiers" in project
    assert "keywords" in project
    assert "build>=1.2.2" in project["optional-dependencies"]["dev"]
    assert "twine>=6.1.0" in project["optional-dependencies"]["dev"]


def test_readme_uses_generic_public_examples() -> None:
    readme = Path("README.md").read_text()

    assert '"node-a": "cluster-a.config"' in readme
    assert '"edge": "edge-cluster.config"' in readme
    assert '"K8S_KUBECONFIG_DIR": "/path/to/.kube"' in readme
    assert '"command": "k8s-mcp-server"' in readme
