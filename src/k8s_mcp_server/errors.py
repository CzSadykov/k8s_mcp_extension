"""Custom exceptions for the K8s MCP extension."""

from typing import Any

from k8s_mcp_server.tools import CommandResult, ErrorDetails, ErrorDetailsNested


class K8sMCPError(Exception):
    """Base exception for extension-specific errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class CommandValidationError(K8sMCPError):
    """Raised when a command does not pass validation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, "VALIDATION_ERROR", details)


class CommandExecutionError(K8sMCPError):
    """Raised when a command exits unsuccessfully."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, "EXECUTION_ERROR", details)


class CommandTimeoutError(K8sMCPError):
    """Raised when a command exceeds the configured timeout."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, "TIMEOUT_ERROR", details)


def create_error_result(
    error: K8sMCPError,
    command: str | None = None,
    exit_code: int | None = None,
    stderr: str | None = None,
) -> CommandResult:
    """Convert an exception into a structured command result."""

    nested_details = ErrorDetailsNested()
    if command:
        nested_details["command"] = command
    if exit_code is not None:
        nested_details["exit_code"] = exit_code
    if stderr:
        nested_details["stderr"] = stderr

    for key, value in error.details.items():
        if key not in nested_details:
            nested_details[key] = value

    error_details = ErrorDetails(
        message=str(error),
        code=error.code,
        details=nested_details,
    )

    return CommandResult(
        status="error",
        output=str(error),
        exit_code=exit_code or 1,
        error=error_details,
    )
