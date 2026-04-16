# K8s MCP Server

MCP server for Kubernetes command execution, node inspection, and node-level diagnostics. Extension of [k8s-mcp-server](https://github.com/alexei-led/k8s-mcp-server) by alexei-led.

## Features

- validated wrappers around `kubectl`, `helm`, `istioctl`, and `argocd`
- node-aware kubeconfig selection through `K8S_NODE_PREFIX_MAPPING`
- `run_checkup_on_node` for `kubectl node-shell ... checkup -n`
- `get_logs_on_node` for collecting `dmesg`, `journalctl`, `/var/log/*`, and `/var/crash`
- Kubernetes node inspection tools for status, labels, pods, and resources

## Configuration

Set `K8S_NODE_PREFIX_MAPPING` to a JSON object that maps a node prefix to a kubeconfig file name:

```json
{
  "node-a": "cluster-a.config",
  "edge": "edge-cluster.config"
}
```

The kubeconfig files are resolved relative to `K8S_KUBECONFIG_DIR`, which defaults to `~/.kube`.

## Example MCP Client Configuration

```json
{
  "mcpServers": {
    "k8s-server": {
      "command": "k8s-mcp-server",
      "cwd": "/absolute/path/to/project",
      "env": {
        "K8S_KUBECONFIG_DIR": "/path/to/.kube",
        "K8S_NODE_PREFIX_MAPPING": "{\"node-a\": \"cluster-a.config\", \"edge\": \"edge-cluster.config\"}",
        "K8S_MCP_TIMEOUT": "600"
      }
    }
  }
}
```

## Development

Create the environment and run checks:

```bash
uv sync --extra dev
.venv/bin/python -m pytest
.venv/bin/python -m ruff check
```

Run the server locally:

```bash
.venv/bin/python -m k8s_mcp_server
```
