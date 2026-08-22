from contextlib import asynccontextmanager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

HIGGSFIELD_MCP_URL = "https://mcp.higgsfield.ai/mcp"


@asynccontextmanager
async def higgsfield_session():
    async with streamable_http_client(
        HIGGSFIELD_MCP_URL
    ) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:
            await session.initialize()
            yield session