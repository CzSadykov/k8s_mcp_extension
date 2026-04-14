"""Shared types for command-oriented tools."""

from dataclasses import dataclass, field
from typing import Literal, NotRequired, TypedDict

Severity = Literal["info", "warning", "critical"]


class ErrorDetailsNested(TypedDict, total=False):
    """Nested error details."""

    command: str
    exit_code: int
    stderr: str


class ErrorDetails(TypedDict, total=False):
    """Structured error details."""

    message: str
    code: str
    details: ErrorDetailsNested


class CommandResult(TypedDict):
    """Command execution result."""

    status: Literal["success", "error"]
    output: str
    exit_code: NotRequired[int]
    execution_time: NotRequired[float]
    error: NotRequired[ErrorDetails]


class NodeCheckupResult(TypedDict, total=False):
    """Structured result of node checkup execution."""

    status: Literal["success", "error"]
    node_name: str
    kubeconfig: str
    output: str
    raw_output: str
    error: str
    details: str


@dataclass(frozen=True)
class CommandHelpResult:
    """CLI help result."""

    help_text: str
    status: str = "success"
    error: ErrorDetails | None = None


@dataclass(frozen=True)
class LogAnalysisResult:
    """Structured summary of collected node logs."""

    summary: str
    severity: Severity
    findings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class NodeLogsResult:
    """Full result of node log collection."""

    node_name: str
    kubeconfig_name: str
    raw_logs: str
    analysis: LogAnalysisResult
