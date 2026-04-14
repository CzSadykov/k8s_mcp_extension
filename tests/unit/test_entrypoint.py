"""Tests for the package entrypoint."""

from __future__ import annotations

from types import SimpleNamespace

from k8s_mcp_server import __main__ as entrypoint


def test_main_runs_startup_checks_before_server(monkeypatch) -> None:
    call_order: list[str] = []

    monkeypatch.setattr(entrypoint, "ensure_required_tools", lambda: call_order.append("checks"))
    monkeypatch.setattr(entrypoint, "mcp", SimpleNamespace(run=lambda: call_order.append("run")))

    entrypoint.main()

    assert call_order == ["checks", "run"]
