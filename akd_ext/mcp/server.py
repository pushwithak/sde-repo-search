"""FastMCP Server for akd-ext tools."""

from fastmcp import FastMCP
from loguru import logger

from akd_ext.mcp.registry import MCPToolRegistry
from akd_ext.mcp.converter import tool_converter, register_mcp_tool
from akd.tools._base import BaseTool

# Create MCP server
mcp = FastMCP("akd-ext-tools")


def register_all_tools():
    """
    Auto-discover and register all @mcp_tool decorated classes.

    This function imports the tools module to trigger decorator registration,
    then converts and registers each tool with the FastMCP server.

    Example:
        register_all_tools()
    """
    # Import tools module to trigger @mcp_tool decorator registration
    # This must be done inside the function to avoid circular imports
    import akd_ext.tools  # noqa: F401

    # Get all registered tool classes from singleton registry
    tool_classes = MCPToolRegistry().get_tools()

    registered = 0
    for tool_class in tool_classes:
        # Isolate each tool: a construction failure (e.g. a required env var
        # missing for one tool's config) must not abort registration of the
        # others, which would take the whole server down.
        try:
            tool = tool_class()
            # Convert tool to FastMCP compatible function
            mcp_func = tool_converter(tool)
            # Register tool with FastMCP server
            register_mcp_tool(mcp_func, mcp)
            registered += 1
        except Exception as e:
            logger.warning(f"Skipping tool {tool_class.__name__}: failed to register ({e})")

    # Partial failure is tolerated above, but zero tools means a systemic problem
    # (e.g. a broken dependency). Fail loudly so the build is rejected and the
    # previous deployment keeps serving, rather than shipping an empty server.
    if tool_classes and registered == 0:
        raise RuntimeError("No MCP tools registered; refusing to start an empty server.")


def register_tools_manually(tools: list[type[BaseTool]]) -> None:
    """
    Register tools manually without @mcp_tool decorator.

    Args:
        tools: List of BaseTool subclasses to register.

    Example:
        register_tools_manually(tools=[ReverseTool, InternalTool])
    """
    for tool_class in tools:
        tool = tool_class()
        mcp_func = tool_converter(tool)
        register_mcp_tool(mcp_func, mcp)


register_all_tools()
# register_tools_manually(tools=[])  # Add tools here if needed

if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Run akd-ext MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport type (default: stdio, or MCP_TRANSPORT env var)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Host to bind to for SSE (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8000")),
        help="Port for SSE transport (default: 8000)",
    )
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run()
