"""
AClimate MCP Server
Expose AClimate API v3 to AI using MCP protocol
"""

from __future__ import annotations

import logging
import sys

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from mcp.server.fastmcp import FastMCP

from aclimatesdkpy.aclimate_client import AClimateClient, get_client
from aclimatesdkpy.context_builder import ContextBuilder

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


# ── SHARED CLIENT ─────────────────────────────────────────────────────────────
# The SDK's get_client() is an idempotent singleton: the first call inside the
# running event loop opens the httpx.AsyncClient, later calls reuse it. Resolving
# it lazily (instead of at import time) keeps the HTTP pool bound to the loop
# that actually serves the requests.
async def provide_client() -> AClimateClient:
    """Return the shared AClimate client, creating it on first use."""
    return await get_client(
        base_url=settings.api_base_url,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
    )


# NOTE: the shared client is NOT opened/closed through a FastMCP lifespan.
# Two reasons, both verified against this project:
#   1. Under streamable-http and sse, FastMCP runs the lifespan once per MCP
#      SESSION, not once per process. Closing the SDK singleton there tears it
#      down for every session still running ("AssertionError: Client not
#      initialized").
#   2. `mcp dev` / `mcp run` load this file with importlib without registering
#      it in sys.modules; combined with `from __future__ import annotations`,
#      any @dataclass declared here fails with
#      "AttributeError: 'NoneType' object has no attribute '__dict__'".
# The lazy provider above is enough: the pool is created on first use inside the
# serving loop and released when the process exits (SDK atexit hook).
mcp = FastMCP(
    settings.server_name,
    log_level=settings.log_level.upper(),
    host=settings.mcp_host,
    port=settings.mcp_port,
)

# ── REGISTRO CENTRALIZADO ─────────────────────────────────────────────────────
# ContextBuilder turns raw API records into short narratives so time-series
# tools do not flood the agent's context window (see tools.py detail param).
context_builder = ContextBuilder(settings.language)

register_resources(mcp=mcp, get_client=provide_client)
register_tools(mcp=mcp, get_client=provide_client, ctx=context_builder)
register_prompts(mcp=mcp)

# ── WEB PAGE ──────────────────────────────────────────────────────────────────
@mcp.custom_route("/", methods=["GET"])
async def index(request: Request) -> HTMLResponse:
    html = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>AClimate MCP</title>
      </head>
      <body style="font-family: Arial, sans-serif; padding: 40px;">
        <h1>MCP Running</h1>
        <p><strong>Server:</strong> AClimate MCP</p>
        <p><strong>Transport:</strong> {settings.mcp_transport}</p>
        <ul>
          <li><a href="/health">/health</a></li>
          <li><code>/mcp</code> for streamable-http</li>
          <li><code>/sse</code> for sse</li>
        </ul>
      </body>
    </html>
    """
    return HTMLResponse(html)

@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "service": settings.server_name,
            "transport": settings.mcp_transport,
            "api_base_url": settings.api_base_url,
            "host": settings.mcp_host,
            "port": settings.mcp_port,
        }
    )


@mcp.custom_route("/healt", methods=["GET"])
async def health_typo_alias(request: Request) -> JSONResponse:
    return await health(request)

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main() -> None:
    logger.info(
            "AClimate MCP started — API: %s - MODE: %s",
            settings.api_base_url,
            settings.mcp_transport,
        )
    
    if settings.mcp_transport == "streamable-http":
        mcp.run(transport="streamable-http",mount_path="/mcp",)
    elif settings.mcp_transport == "sse":
        mcp.run(transport="sse",mount_path="/sse",)
    else:
        mcp.run(transport="stdio")
    """
    async def run() -> None:
        logger.info(
            "AClimate MCP started — API: %s - MODE: %s",
            settings.api_base_url,
            settings.mcp_transport,
        )
        #await mcp.run_sse_async()
        
        if settings.mcp_transport == "streamable-http":
            #await mcp.run_async(transport="streamable-http",host=settings.mcp_host,port=settings.mcp_port,)
            await mcp.run_streamable_http_async()
        elif settings.mcp_transport == "sse":
            #await mcp.run_async(transport="sse",host=settings.mcp_host,port=settings.mcp_port,)
            await mcp.run_sse_async()
        else:
            print("Using stdio transport. This is not recommended for production.")
            #await mcp.run_async(transport="stdio")
            await mcp.run_sse_async()
        

    asyncio.run(run())
    """


if __name__ == "__main__":
    main()