"""Run an isolated uvx installation of the built wheel through real MCP stdio."""

import asyncio
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    wheel = next((root / "dist").glob("*.whl"))
    env = {k: v for k, v in os.environ.items() if k != "AGENTSCOPE_API_KEY"}
    params = StdioServerParameters(
        command="uvx",
        args=["--isolated", "--from", str(wheel), "agentscope-media-mcp"],
        env=env,
    )
    async with (
        stdio_client(params) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("list_models", {})
        assert len(tools.tools) == 9
        assert not result.isError
        assert len(result.structuredContent["models"]) == 9
        print("Isolated wheel: MCP initialized, 9 tools, 9 models, no API Key required.")


asyncio.run(main())
