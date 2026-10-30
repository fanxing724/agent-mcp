import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_real_stdio_lifecycle_and_error():
    env = dict(os.environ)
    env.pop("AGENTSCOPE_API_KEY", None)
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "agentscope_media_mcp"], env=env
    )
    async with (
        stdio_client(params) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        listing = await session.list_tools()
        assert len(listing.tools) == 9
        tools = {t.name: t for t in listing.tools}
        assert "ctx" not in tools["generate_video"].inputSchema["properties"]
        result = await session.call_tool("list_models", {})
        assert not result.isError
        assert len(result.structuredContent["models"]) == 9
        error = await session.call_tool("generate_image", {"prompt": "A tree"})
        assert error.isError
        assert "configuration_missing" in error.content[0].text
