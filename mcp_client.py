"""
MCP client helper.

Spawns an MCP server as a subprocess, calls one tool, and returns the result.
A new subprocess is started per call — fine for a demo, use a persistent
session for production.
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def _call(server_script: str, tool_name: str, arguments: dict) -> str:
    params = StdioServerParameters(command=sys.executable, args=[server_script])
    devnull = open(os.devnull, "w")
    try:
        async with stdio_client(params, errlog=devnull) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                for block in result.content:
                    if hasattr(block, "text"):
                        return block.text
                return str(result.content)
    finally:
        devnull.close()


def call_mcp(server_script: str, tool_name: str, **kwargs) -> str:
    """Synchronous entry point for use inside tools.py."""
    return asyncio.run(_call(server_script, tool_name, kwargs))
