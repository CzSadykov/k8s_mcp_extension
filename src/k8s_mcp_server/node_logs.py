"""Node log collection contracts and heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from k8s_mcp_server.tools import LogAnalysisResult

DATE_FORMAT = "%Y-%m-%d %H:%M:%S %Z"

# Inner script for `xargs -I {} sh -c '...'` when reading newest /var/crash dmesg (audit lines excluded).
_VAR_CRASH_FIND_DMESG = (
    'if [ -n "{}" ]; then grep -v "audit\\|AUDIT" {}/dmesg.* 2>/dev/null || '
    'echo "No dmesg files found in {}"; else echo "No crash directories found"; fi'
)


@dataclass(frozen=True)
class NodeLogCollectionRequest:
    """Parameters for collecting logs from a node."""

    node_name: str
    since: datetime | None = None
    until: datetime | None = None
    include_crash_directory: bool = True


@dataclass(frozen=True)
class NodeCrashLogCollectionRequest:
    """Parameters for collecting crash logs from a node."""

    node_name: str


class NodeLogCommandBuilder:
    """Build a remote collection script executed through node-shell."""

    def build(self, request: NodeLogCollectionRequest) -> str:
        """Build a shell script for collecting logs on a node."""

        since_clause = ""
        until_clause = ""
        if request.since:
            since_clause = f"--since '{request.since.strftime(DATE_FORMAT)}'"
        if request.until:
            until_clause = f"--until '{request.until.strftime(DATE_FORMAT)}'"

        crash_collection = ""
        if request.include_crash_directory:
            crash_collection = f"""
echo '===== /var/crash ====='
if [ -d /var/crash ]; then
  find /var/crash -maxdepth 1 -type d | sort -r | head -n 1 | xargs -I {{}} sh -c '{_VAR_CRASH_FIND_DMESG}'
else
  echo '/var/crash directory is absent'
fi
"""

        return f"""
set -eu
echo '===== dmesg ====='
dmesg -T || true
echo '===== kernel journal ====='
journalctl -k {since_clause} {until_clause} || true
echo '===== system journal ====='
journalctl {since_clause} {until_clause} || true
echo '===== /var/log/syslog ====='
test -f /var/log/syslog && tail -n 400 /var/log/syslog || true
echo '===== /var/log/messages ====='
test -f /var/log/messages && tail -n 400 /var/log/messages || true
echo '===== /var/log/kern.log ====='
test -f /var/log/kern.log && tail -n 400 /var/log/kern.log || true
{crash_collection}
""".strip()


class NodeCrashLogCommandBuilder:
    """Build a remote collection script executed through node-shell for crash logs only.

    This builder collects crash logs from /var/crash directory, focusing on dmesg files
    while excluding audit-related entries to reduce noise in reboot cause analysis.
    """

    def build(self, request: NodeCrashLogCollectionRequest) -> str:
        """Build a shell script for collecting crash logs on a node."""

        return f"""
set -eu
echo '===== /var/crash ====='
if [ -d /var/crash ]; then
  echo "Crash directory exists. Contents:"
  ls -la /var/crash
  echo "Detailed crash information (excluding audit entries):"
  find /var/crash -maxdepth 1 -type d | sort -r | head -n 1 | xargs -I {{}} sh -c '{_VAR_CRASH_FIND_DMESG}'
else
  echo '/var/crash directory is absent'
fi
""".strip()


class LogAnalyzer:
    """Perform lightweight heuristic analysis over collected node logs."""

    _PATTERN_SEVERITY: tuple[tuple[str, str, str], ...] = (
        ("kernel panic", "critical", "Detected kernel panic markers in node logs."),
        ("panic - not syncing", "critical", "Kernel reported panic without syncing."),
        ("bug:", "critical", "Kernel BUG markers were found."),
        ("call trace", "warning", "Kernel call traces are present and usually indicate instability."),
        ("out of memory", "warning", "Out-of-memory conditions were detected."),
        ("oom-killer", "warning", "OOM killer activity was detected."),
        ("reboot", "warning", "Reboot-related events were detected around the failure window."),
        ("watchdog", "warning", "Watchdog resets or stalls were detected."),
        ("i/o error", "warning", "Disk or device I/O errors were found."),
        ("segfault", "warning", "Segmentation faults were found in system logs."),
    )

    def analyze(self, raw_logs: str) -> LogAnalysisResult:
        """Summarize relevant findings from raw logs."""

        lowered_logs = raw_logs.lower()
        findings: list[str] = []
        severity = "info"

        for pattern, candidate_severity, message in self._PATTERN_SEVERITY:
            if pattern in lowered_logs:
                findings.append(message)
                severity = self._pick_severity(severity, candidate_severity)

        if not findings:
            return LogAnalysisResult(
                summary="No critical node-level signals were detected in the collected logs.",
                severity="info",
                findings=(),
            )

        summary = self._build_summary(findings=findings, severity=severity)
        return LogAnalysisResult(summary=summary, severity=severity, findings=tuple(findings))

    @staticmethod
    def _pick_severity(current: str, candidate: str) -> str:
        order = {"info": 0, "warning": 1, "critical": 2}
        return candidate if order[candidate] > order[current] else current

    @staticmethod
    def _build_summary(findings: list[str], severity: str) -> str:
        joined_findings = " ".join(dict.fromkeys(findings))
        prefix = {
            "critical": "Critical node instability indicators were found.",
            "warning": "Suspicious node-level signals were found.",
            "info": "Logs were collected successfully.",
        }[severity]
        return f"{prefix} {joined_findings}"
