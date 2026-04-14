"""Execution utilities for supported Kubernetes CLIs."""

from __future__ import annotations

import asyncio
import logging
import shlex
import time
from asyncio.subprocess import PIPE

from k8s_mcp_server.config import DEFAULT_TIMEOUT, MAX_OUTPUT_SIZE, SUPPORTED_CLI_TOOLS
from k8s_mcp_server.errors import CommandExecutionError, CommandTimeoutError, CommandValidationError
from k8s_mcp_server.security import validate_command
from k8s_mcp_server.tools import CommandHelpResult, CommandResult

LOG = logging.getLogger(__name__)


async def check_cli_installed(cli_tool: str) -> bool:
    """Check whether a CLI tool is available in PATH."""

    tool_config = SUPPORTED_CLI_TOOLS.get(cli_tool)
    if tool_config is None:
        return False

    try:
        process = await asyncio.create_subprocess_exec(
            *shlex.split(tool_config["check_cmd"]),
            stdout=PIPE,
            stderr=PIPE,
        )
    except FileNotFoundError:
        LOG.info("%s is not installed or not available in PATH", cli_tool)
        return False

    await process.communicate()
    return process.returncode == 0


async def execute_command(command: str, timeout: int | None = None) -> CommandResult:
    """Execute a validated command string."""

    try:
        validate_command(command)
    except ValueError as error:
        raise CommandValidationError(str(error), details={"command": command}) from error

    actual_timeout = timeout or DEFAULT_TIMEOUT
    start_time = time.monotonic()
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=PIPE,
        stderr=PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=actual_timeout)
    except TimeoutError as error:
        process.kill()
        raise CommandTimeoutError(
            f"Command timed out after {actual_timeout} seconds",
            details={"command": command, "timeout": actual_timeout},
        ) from error

    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")

    if len(stdout_text) > MAX_OUTPUT_SIZE:
        stdout_text = stdout_text[:MAX_OUTPUT_SIZE] + "\n... (output truncated)"

    if process.returncode != 0:
        raise CommandExecutionError(
            stderr_text or "Command failed",
            details={
                "command": command,
                "exit_code": process.returncode,
                "stderr": stderr_text,
            },
        )

    return CommandResult(
        status="success",
        output=stdout_text,
        exit_code=process.returncode,
        execution_time=time.monotonic() - start_time,
    )


async def get_command_help(cli_tool: str, command: str | None = None) -> CommandHelpResult:
    """Return CLI help output for a supported tool."""

    tool_config = SUPPORTED_CLI_TOOLS.get(cli_tool)
    if tool_config is None:
        return CommandHelpResult(help_text=f"Unsupported CLI tool: {cli_tool}", status="error")

    help_command = f"{cli_tool} {command} {tool_config['help_flag']}" if command else f"{cli_tool} {tool_config['help_flag']}"
    try:
        result = await execute_command(help_command)
    except (CommandValidationError, CommandExecutionError, CommandTimeoutError) as error:
        LOG.warning("Failed to collect help for %s: %s", cli_tool, error)
        return CommandHelpResult(
            help_text=str(error),
            status="error",
            error={"message": str(error), "code": getattr(error, "code", "INTERNAL_ERROR")},
        )
    return CommandHelpResult(help_text=result["output"])
