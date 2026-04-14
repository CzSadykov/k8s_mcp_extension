"""Module entrypoint."""

from k8s_mcp_server.server import ensure_required_tools, mcp


def main() -> None:
    """Run the MCP server with the configured transport."""

    ensure_required_tools()
    mcp.run()


if __name__ == "__main__":
    main()
