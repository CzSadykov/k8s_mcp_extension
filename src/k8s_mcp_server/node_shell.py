"""Node-shell command builders and service layer."""

from __future__ import annotations

import asyncio
import logging
import shlex
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from k8s_mcp_server.config import DEFAULT_TIMEOUT, KUBECONFIG_DIR, MAX_OUTPUT_SIZE
from k8s_mcp_server.errors import CommandExecutionError, CommandTimeoutError
from k8s_mcp_server.node_context import NodeContextResolver
from k8s_mcp_server.node_logs import LogAnalyzer, NodeLogCollectionRequest, NodeLogCommandBuilder, NodeCrashLogCommandBuilder
from k8s_mcp_server.tools import CommandResult, NodeCheckupResult, NodeLogsResult

LOG = logging.getLogger(__name__)


class AsyncCommandExecutor(Protocol):
    """Abstraction over async subprocess execution."""

    async def run(self, args: Sequence[str], timeout: int | None = None) -> CommandResult:
        """Run a command and return a structured result."""


class SubprocessCommandExecutor:
    """Execute commands via asyncio subprocess APIs."""

    async def run(self, args: Sequence[str], timeout: int | None = None) -> CommandResult:
        actual_timeout = timeout or DEFAULT_TIMEOUT
        start_time = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=actual_timeout)
        except TimeoutError as error:
            process.kill()
            raise CommandTimeoutError(
                f"Command timed out after {actual_timeout} seconds",
                details={"command": shlex.join(args), "timeout": actual_timeout},
            ) from error

        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")

        if len(stdout_text) > MAX_OUTPUT_SIZE:
            stdout_text = stdout_text[:MAX_OUTPUT_SIZE] + "\n... (output truncated)"

        if process.returncode != 0:
            raise CommandExecutionError(
                stderr_text or "Command failed",
                details={
                    "command": shlex.join(args),
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


@dataclass(frozen=True)
class NodeCommandFactory:
    """Build commands executed through kubectl node-shell."""

    context_resolver: NodeContextResolver
    kubeconfig_dir: str | Path = KUBECONFIG_DIR

    def build_checkup_command(self, node_name: str) -> list[str]:
        """Build the node-shell command for `checkup -n`."""

        kubeconfig_name = self.context_resolver.resolve_context(node_name)
        return [
            "env",
            f"KUBECONFIG={self._resolve_kubeconfig_path(kubeconfig_name)}",
            "kubectl",
            "node-shell",
            node_name,
            "--",
            "bash",
            "-c",
            "checkup -n",
        ]

    def build_probe_command(self, node_name: str) -> list[str]:
        """Build a lightweight probe command for node-shell connectivity."""

        kubeconfig_name = self.context_resolver.resolve_context(node_name)
        return [
            "env",
            f"KUBECONFIG={self._resolve_kubeconfig_path(kubeconfig_name)}",
            "kubectl",
            "node-shell",
            node_name,
            "--",
            "echo",
            "test",
        ]

    def build_log_collection_command(self, request: NodeLogCollectionRequest) -> tuple[list[str], str]:
        """Build the node-shell command that gathers logs."""

        kubeconfig_name = self.context_resolver.resolve_context(request.node_name)
        script = NodeLogCommandBuilder().build(request)
        command = [
            "env",
            f"KUBECONFIG={self._resolve_kubeconfig_path(kubeconfig_name)}",
            "kubectl",
            "node-shell",
            request.node_name,
            "--",
            "sh",
            "-lc",
            script,
        ]
        return command, kubeconfig_name

    def _resolve_kubeconfig_path(self, kubeconfig_name: str) -> str:
        kubeconfig_dir = Path(self.kubeconfig_dir).expanduser()
        return str(kubeconfig_dir / kubeconfig_name)


@dataclass
class NodeDiagnosticsService:
    """Orchestrate node-level diagnostic actions."""

    command_factory: NodeCommandFactory
    executor: AsyncCommandExecutor
    analyzer: LogAnalyzer

    async def run_checkup(self, node_name: str, timeout: int | None = None) -> NodeCheckupResult:
        """Run `checkup -n` on a node."""

        probe_command = self.command_factory.build_probe_command(node_name)
        await self.executor.run(probe_command, timeout=30)
        command = self.command_factory.build_checkup_command(node_name)
        kubeconfig_name = self.command_factory.context_resolver.resolve_context(node_name)
        LOG.info("Running checkup on node %s", node_name)
        result = await self.executor.run(command, timeout=timeout or 120)
        processed_output = self._trim_checkup_output(result["output"])
        return NodeCheckupResult(
            status="success",
            node_name=node_name,
            kubeconfig=kubeconfig_name,
            output=processed_output,
            raw_output=result["output"],
            error="",
            details="",
        )

    async def collect_logs(self, request: NodeLogCollectionRequest, timeout: int | None = None) -> NodeLogsResult:
        """Collect logs and derive a summary."""

        command, kubeconfig_name = self.command_factory.build_log_collection_command(request)
        LOG.info("Collecting logs on node %s", request.node_name)
        result = await self.executor.run(command, timeout=timeout)
        analysis = self.analyzer.analyze(result["output"])
        return NodeLogsResult(
            node_name=request.node_name,
            kubeconfig_name=kubeconfig_name,
            raw_logs=result["output"],
            analysis=analysis,
        )

    async def collect_crash_logs(self, request: NodeCrashLogCollectionRequest, timeout: int | None = None) -> dict[str, object]:
        """Collect crash logs only."""

        # Build the command for crash log collection
        kubeconfig_name = self.command_factory.context_resolver.resolve_context(request.node_name)
        script = NodeCrashLogCommandBuilder().build(request)
        command = [
            "env",
            f"KUBECONFIG={self.command_factory._resolve_kubeconfig_path(kubeconfig_name)}",
            "kubectl",
            "node-shell",
            request.node_name,
            "--",
            "sh",
            "-lc",
            script,
        ]

        LOG.info("Collecting crash logs on node %s", request.node_name)
        result = await self.executor.run(command, timeout=timeout)

        return {
            "node_name": request.node_name,
            "kubeconfig_name": kubeconfig_name,
            "raw_logs": result["output"],
        }

    @staticmethod
    def _trim_checkup_output(output: str) -> str:
        lines = output.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-2])
        if len(lines) >= 1:
            return "\n".join(lines[1:])
        return output
