"""
AClimate MCP Server
Expone la API v3 de AClimate al ecosistema de IA a través del protocolo MCP.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from aclimatesdkpy.context_builder import ContextBuilder
from aclimatesdkpy.aclimate_client import get_client


from aclimate_mcp.settings import Settings
from aclimate_mcp.resources import register_resources
from aclimate_mcp.tools import register_tools
from aclimate_mcp.prompts import register_prompts

# ── Setup ─────────────────────────────────────────────────────────────────────
settings = Settings()  # type: ignore[call-arg]

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("aclimate_mcp")

mcp = FastMCP(settings.server_name, log_level=settings.log_level.upper())
ctx = ContextBuilder()


# El cliente se inicializa en el lifespan del servidor
async def shared_client():
    return await get_client(
        base_url=settings.api_base_url,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
    )

# ── Helpers ───────────────────────────────────────────────────────────────────

async def cached_get(cache_key: str, path: str, **params: Any) -> Any:
    """GET automatic cache."""
    #cached = await cache.get(cache_key)
    #if cached is not None:
    #    return cached
    #data = await get_client().get(path, **params)
    client = await get_client(
        base_url=settings.api_base_url,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
    )
    data = await client.get(path, **params)
    #await cache.set(cache_key, data)
    return data

# ── REGISTRO CENTRALIZADO ─────────────────────────────────────────────────────
register_resources(mcp=mcp, cached_get=cached_get)
register_tools(mcp=mcp, cached_get=cached_get, ctx=ctx, get_client=get_client)
register_prompts(mcp=mcp)


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main() -> None:
    async def run() -> None:
        logger.info(
            "AClimate MCP started — API: %s - MODE: %s",
            settings.api_base_url,
            settings.mcp_transport,
        )
        #await mcp.run_sse_async()
        
        if settings.mcp_transport == "streamable-http":
            await mcp.run_async(transport="streamable-http",host=settings.mcp_host,port=settings.mcp_port,)
        elif settings.mcp_transport == "sse":
            await mcp.run_async(transport="sse",host=settings.mcp_host,port=settings.mcp_port,)
        else:
            await mcp.run_async(transport="stdio")
        

    asyncio.run(run())


if __name__ == "__main__":
    main()