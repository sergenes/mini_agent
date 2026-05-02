"""
Minimal MCP server — demonstrates the Model Context Protocol.

Exposes two tools over stdio using the FastMCP high-level API.
The agent connects to this as a subprocess; communication happens
via JSON-RPC messages on stdin/stdout.

Run standalone to verify it starts:
    python mcp_server.py
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mini-tools")


@mcp.tool()
def to_uppercase(text: str) -> str:
    """Convert text to uppercase."""
    return text.upper()


@mcp.tool()
def count_words(text: str) -> int:
    """Count the number of words in a string."""
    return len(text.split())


if __name__ == "__main__":
    mcp.run()
