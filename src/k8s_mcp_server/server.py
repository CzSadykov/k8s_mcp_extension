"""FastMCP server with Kubernetes CLI and node diagnostics tools."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from pydantic import Field

from k8s_mcp_server import __version__
from k8s_mcp_server.cli_executor import check_cli_installed, execute_command, get_command_help
from k8s_mcp_server.config import DEFAULT_TIMEOUT, INSTRUCTIONS, SUPPORTED_CLI_TOOLS
from k8s_mcp_server.kubernetes_node import KubernetesNodeService
from k8s_mcp_server.node_context import NodeContextResolver
from k8s_mcp_server.node_logs import LogAnalyzer, NodeLogCollectionRequest
from k8s_mcp_server.node_shell import NodeCommandFactory, NodeDiagnosticsService, SubprocessCommandExecutor
from k8s_mcp_server.tools import CommandHelpResult, CommandResult, NodeCheckupResult

LOG = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import Context, FastMCP
except ModuleNotFoundError as error:  # pragma: no cover - exercised only without runtime deps
    raise RuntimeError("Install project dependencies before importing k8s_mcp_server.server") from error


def run_startup_checks() -> dict[str, bool]:
    """Check tool availability before serving requests."""

    cli_status: dict[str, bool] = {}
    for cli_tool in SUPPORTED_CLI_TOOLS:
        cli_status[cli_tool] = asyncio.run(check_cli_installed(cli_tool))
    return cli_status


cli_status: dict[str, bool] = {}
mcp = FastMCP(name="K8s MCP Server", instructions=INSTRUCTIONS)
mcp._mcp_server.version = __version__

_node_service = NodeDiagnosticsService(
    command_factory=NodeCommandFactory(context_resolver=NodeContextResolver.default()),
    executor=SubprocessCommandExecutor(),
    analyzer=LogAnalyzer(),
)
_node_info_service = KubernetesNodeService(context_resolver=NodeContextResolver.default())


def refresh_cli_status() -> dict[str, bool]:
    """Refresh cached CLI availability information."""

    cli_status.clear()
    cli_status.update(run_startup_checks())
    return dict(cli_status)


def ensure_required_tools() -> None:
    """Validate that the minimum runtime toolchain is available."""

    status = refresh_cli_status()
    if not status.get("kubectl", False):
        raise RuntimeError("kubectl is required but not available")


def _tool_is_available(tool: str) -> bool:
    """Return cached CLI availability, refreshing it on first use."""

    if not cli_status:
        refresh_cli_status()
    return cli_status.get(tool, False)


async def _execute_tool_command(tool: str, command: str, timeout: int | None, ctx: Context | None) -> CommandResult:
    LOG.info("Executing %s command: %s", tool, command)
    if not _tool_is_available(tool):
        raise RuntimeError(f"{tool} is not installed or not in PATH")

    actual_timeout = timeout or DEFAULT_TIMEOUT
    if not command.strip().startswith(tool):
        command = f"{tool} {command}"
    if ctx:
        await ctx.info(f"Executing {tool} command")
    return await execute_command(command, timeout=actual_timeout)


async def _describe_tool_command(tool: str, command: str | None, ctx: Context | None) -> CommandHelpResult:
    LOG.info("Getting %s documentation for %s", tool, command or "general usage")
    if not _tool_is_available(tool):
        raise RuntimeError(f"{tool} is not installed or not in PATH")
    if ctx:
        await ctx.info(f"Fetching {tool} help")
    return await get_command_help(tool, command)


@mcp.tool()
async def describe_kubectl(
    command: str | None = Field(default=None, description="Specific kubectl command to get help for"),
    ctx: Context | None = None,
) -> CommandHelpResult:
    """Get help text for kubectl."""

    return await _describe_tool_command("kubectl", command, ctx)


@mcp.tool()
async def describe_helm(
    command: str | None = Field(default=None, description="Specific Helm command to get help for"),
    ctx: Context | None = None,
) -> CommandHelpResult:
    """Get help text for Helm."""

    return await _describe_tool_command("helm", command, ctx)


@mcp.tool()
async def describe_istioctl(
    command: str | None = Field(default=None, description="Specific Istio command to get help for"),
    ctx: Context | None = None,
) -> CommandHelpResult:
    """Get help text for istioctl."""

    return await _describe_tool_command("istioctl", command, ctx)


@mcp.tool()
async def describe_argocd(
    command: str | None = Field(default=None, description="Specific ArgoCD command to get help for"),
    ctx: Context | None = None,
) -> CommandHelpResult:
    """Get help text for argocd."""

    return await _describe_tool_command("argocd", command, ctx)


@mcp.tool(description="Execute kubectl commands with basic validation and timeout support.")
async def execute_kubectl(
    command: str = Field(description="Complete kubectl command to execute"),
    timeout: int | None = Field(default=None, description="Maximum execution time in seconds"),
    ctx: Context | None = None,
) -> CommandResult:
    """Execute kubectl."""

    return await _execute_tool_command("kubectl", command, timeout, ctx)


@mcp.tool(description="Execute Helm commands with basic validation and timeout support.")
async def execute_helm(
    command: str = Field(description="Complete Helm command to execute"),
    timeout: int | None = Field(default=None, description="Maximum execution time in seconds"),
    ctx: Context | None = None,
) -> CommandResult:
    """Execute helm."""

    return await _execute_tool_command("helm", command, timeout, ctx)


@mcp.tool(description="Execute istioctl commands with basic validation and timeout support.")
async def execute_istioctl(
    command: str = Field(description="Complete istioctl command to execute"),
    timeout: int | None = Field(default=None, description="Maximum execution time in seconds"),
    ctx: Context | None = None,
) -> CommandResult:
    """Execute istioctl."""

    return await _execute_tool_command("istioctl", command, timeout, ctx)


@mcp.tool(description="Execute argocd commands with basic validation and timeout support.")
async def execute_argocd(
    command: str = Field(description="Complete argocd command to execute"),
    timeout: int | None = Field(default=None, description="Maximum execution time in seconds"),
    ctx: Context | None = None,
) -> CommandResult:
    """Execute argocd."""

    return await _execute_tool_command("argocd", command, timeout, ctx)


@mcp.tool(description="Run `checkup -n` on a node via node-shell using a kubeconfig selected from node prefix.")
async def run_checkup_on_node(
    node_name: str = Field(description="Node name, for example `node-a-worker-01`"),
    timeout: int | None = Field(default=None, description="Maximum execution time in seconds"),
    ctx: Context | None = None,
) -> NodeCheckupResult:
    """Run `checkup -n` through kubectl node-shell."""

    if ctx:
        await ctx.info(f"Running checkup on node {node_name}")
    return await _node_service.run_checkup(node_name=node_name, timeout=timeout)


def _parse_window(
    since: str | None,
    until: str | None,
    lookback_hours: int,
) -> tuple[datetime | None, datetime | None]:
    parsed_until = datetime.fromisoformat(until).astimezone(UTC) if until else datetime.now(tz=UTC)
    parsed_since = datetime.fromisoformat(since).astimezone(UTC) if since else parsed_until - timedelta(hours=lookback_hours)
    return parsed_since, parsed_until


@mcp.tool(description="Collect node-level logs from /var/log, /var/crash, dmesg, and journalctl, then return a summary.")
async def get_logs_on_node(
    node_name: str = Field(description="Node name, for example `node-a-worker-01`"),
    since: str | None = Field(default=None, description="Start of interval in ISO-8601 format"),
    until: str | None = Field(default=None, description="End of interval in ISO-8601 format"),
    lookback_hours: int = Field(default=2, description="Fallback time window if `since` is omitted"),
    include_crash_directory: bool = Field(default=True, description="Whether to inspect `/var/crash`"),
    timeout: int | None = Field(default=None, description="Maximum execution time in seconds"),
    ctx: Context | None = None,
) -> dict[str, object]:
    """Collect node logs and return a heuristic summary."""

    parsed_since, parsed_until = _parse_window(since=since, until=until, lookback_hours=lookback_hours)
    request = NodeLogCollectionRequest(
        node_name=node_name,
        since=parsed_since,
        until=parsed_until,
        include_crash_directory=include_crash_directory,
    )
    if ctx:
        await ctx.info(f"Collecting logs on node {node_name}")
    result = await _node_service.collect_logs(request=request, timeout=timeout)
    return {
        "node_name": result.node_name,
        "kubeconfig_name": result.kubeconfig_name,
        "summary": result.analysis.summary,
        "severity": result.analysis.severity,
        "findings": list(result.analysis.findings),
        "raw_logs": result.raw_logs,
    }


@mcp.tool(description="Return Kubernetes node status from the cluster selected by node prefix.")
async def get_node_status(node_name: str = Field(description="Node name")) -> dict[str, object]:
    """Return node conditions and high-level status."""

    return _node_info_service.get_node_status(node_name)


@mcp.tool(description="Return Kubernetes node labels from the cluster selected by node prefix.")
async def get_node_labels(node_name: str = Field(description="Node name")) -> dict[str, object]:
    """Return node labels."""

    return _node_info_service.get_node_labels(node_name)


@mcp.tool(description="Return pods scheduled on a node from the cluster selected by node prefix.")
async def get_pods_on_node(node_name: str = Field(description="Node name")) -> dict[str, object]:
    """Return pods running on a specific node."""

    return _node_info_service.get_pods_on_node(node_name)


@mcp.tool(description="Return node capacity, allocatable resources, and current pod usage.")
async def get_node_resources(node_name: str = Field(description="Node name")) -> dict[str, object]:
    """Return resources for a specific node."""

    return _node_info_service.get_node_resources(node_name)
