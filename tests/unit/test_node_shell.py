"""Tests for node-shell command orchestration."""

from k8s_mcp_server.node_context import NodeContextResolver
from k8s_mcp_server.node_logs import LogAnalyzer
from k8s_mcp_server.node_shell import AsyncCommandExecutor, NodeCommandFactory, NodeDiagnosticsService
from k8s_mcp_server.tools import CommandResult


def test_builds_checkup_command_with_resolved_kubeconfig() -> None:
    resolver = NodeContextResolver(prefix_mapping={"node-a": "cluster-a.config"})
    factory = NodeCommandFactory(context_resolver=resolver, kubeconfig_dir="/tmp/kubeconfigs")

    command = factory.build_checkup_command("node-a-worker-01")

    assert command == [
        "env",
        "KUBECONFIG=/tmp/kubeconfigs/cluster-a.config",
        "kubectl",
        "node-shell",
        "node-a-worker-01",
        "--",
        "bash",
        "-c",
        "checkup -n",
    ]


class FakeExecutor(AsyncCommandExecutor):
    """Test double for subprocess execution."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    async def run(self, args: list[str], timeout: int | None = None) -> CommandResult:
        self.commands.append(args)
        if args[-1] == "echo" or (len(args) >= 2 and args[-2:] == ["echo", "test"]):
            return CommandResult(status="success", output="test\n", exit_code=0, execution_time=0.01)
        return CommandResult(
            status="success",
            output="header\nline-1\nline-2\nfooter-1\nfooter-2\n",
            exit_code=0,
            execution_time=0.02,
        )


async def test_run_checkup_probes_connection_and_trims_wrapper_lines() -> None:
    resolver = NodeContextResolver(prefix_mapping={"node-a": "cluster-a.config"})
    factory = NodeCommandFactory(context_resolver=resolver, kubeconfig_dir="/tmp/kubeconfigs")
    executor = FakeExecutor()
    service = NodeDiagnosticsService(command_factory=factory, executor=executor, analyzer=LogAnalyzer())

    result = await service.run_checkup("node-a-worker-01")

    assert result["status"] == "success"
    assert result["kubeconfig"] == "cluster-a.config"
    assert result["output"] == "line-1\nline-2"
    assert executor.commands[0][-2:] == ["echo", "test"]
