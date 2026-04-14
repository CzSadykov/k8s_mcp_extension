"""Tests for node log collection and analysis."""

from datetime import UTC, datetime

from k8s_mcp_server.node_logs import (
    LogAnalysisResult,
    LogAnalyzer,
    NodeLogCollectionRequest,
    NodeLogCommandBuilder,
)


def test_builds_time_bounded_log_collection_script() -> None:
    request = NodeLogCollectionRequest(
        node_name="node-a-worker-01",
        since=datetime(2026, 4, 14, 10, 0, tzinfo=UTC),
        until=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
        include_crash_directory=True,
    )

    command = NodeLogCommandBuilder().build(request)

    assert "journalctl --since '2026-04-14 10:00:00 UTC'" in command
    assert "--until '2026-04-14 12:00:00 UTC'" in command
    assert "/var/crash" in command
    assert "dmesg -T" in command


def test_summarizes_kernel_panic_and_reboot_signals() -> None:
    analyzer = LogAnalyzer()
    raw_logs = """
    Apr 14 10:31:00 node kernel: BUG: unable to handle kernel NULL pointer dereference
    Apr 14 10:31:01 node kernel: Kernel panic - not syncing: Fatal exception
    Apr 14 10:31:05 node systemd[1]: Starting Reboot...
    """

    result = analyzer.analyze(raw_logs)

    assert isinstance(result, LogAnalysisResult)
    assert "kernel panic" in result.summary.lower()
    assert "reboot" in result.summary.lower()
    assert result.severity == "critical"


def test_summarizes_when_no_known_signals_detected() -> None:
    analyzer = LogAnalyzer()

    result = analyzer.analyze("Apr 14 10:31:00 node kubelet: Started container runtime")

    assert result.severity == "info"
    assert "no critical node-level signals" in result.summary.lower()
