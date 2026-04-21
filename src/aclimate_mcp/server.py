"""
AClimate MCP Server
Expone la API v3 de AClimate al ecosistema de IA a través del protocolo MCP.

Tools disponibles:
  Geo Discovery:
    - list_countries
    - find_country_by_name
    - find_admin_region
    - find_locations
    - get_locations_with_current_data
    - get_point_data_from_coordinates

  Historical Climate:
    - get_daily_climate
    - get_monthly_climate
    - get_climatology
    - get_climate_extremes_daily
    - get_climate_extremes_climatology

  Agro-climate Indicators:
    - list_indicators_by_country
    - get_indicator_history
    - get_indicator_by_name_and_location
    - get_indicator_extremes
    - get_agro_recommendations
    - list_indicator_categories

Resources:
    - aclimate://countries
    - aclimate://indicators/{country_id}
    - aclimate://indicator-categories

Prompts:
    - analyze_climate_risk
    - compare_location_climate
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from aclimate_sdk.aclimate_models import (
    ClimateHistoricalClimatology,
    ClimateHistoricalDaily,
    ClimateHistoricalIndicatorRecord,
    ClimateHistoricalMonthly,
    Country,
    Indicator,
    IndicatorCategory,
    IndicatorFeature,
    Location,
    MinMaxClimatologyRecord,
    MinMaxDailyRecord,
    MinMaxIndicatorRecord,
)
from aclimate_sdk.context_builder import ContextBuilder
#from aclimate_sdk.aclimate_client import AClimateClient
from aclimate_sdk.aclimate_client import get_client, close_client


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
            "AClimate MCP Server iniciado — API: %s",
            settings.api_base_url,
        )
        await mcp.run_sse_async()

    asyncio.run(run())


if __name__ == "__main__":
    main()