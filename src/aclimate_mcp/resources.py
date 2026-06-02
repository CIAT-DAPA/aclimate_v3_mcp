"""
Resources:
    - aclimate://countries
    - aclimate://indicators/{country_id}
    - aclimate://indicator-categories
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aclimatesdkpy.aclimate_client import AClimateClient
from aclimatesdkpy.aclimate_models import (
    Country,
    Indicator,
    IndicatorCategory,
)

# Firma del helper que viene desde server
#CachedGet = Callable[..., Awaitable[Any]]

#def register_resources(mcp, cached_get: CachedGet) -> None:
def register_resources(mcp, client: AClimateClient) -> None:
    # ──────────────────────────────────────────────────────────────────────────
    # RESOURCES
    # ──────────────────────────────────────────────────────────────────────────

    @mcp.resource("aclimate://countries", mime_type="application/json")
    async def list_countries() -> list[Country]:
        """List all countries in AClimate."""
        #data = await cached_get("countries:all", "/countries")
        data = await client.get_countries()
        #return [Country(**c) for c in data]
        return data

    @mcp.resource("aclimate://indicators/categories", mime_type="application/json")
    async def list_indicator_categories() -> list[IndicatorCategory]:
        """List of agroclimatic indicators categories."""
        #data = await cached_get("indicators:categories:all","/indicator-category-mng/all")
        data = await client.get_indicators_all_categories()
        #return [IndicatorCategory(**c) for c in data]
        return data

    @mcp.resource("aclimate://indicators/{country_id}", mime_type="application/json")
    async def list_indicators(country_id: int) -> list[Indicator]:
        """List of all agroclimatic indicators by country."""
        #cache_key = f"indicators:country:{country_id}"
        #data = await cached_get(cache_key,"/indicator-mng/by-country",country_id=country_id,)
        data = await client.get_indicators_by_country(country_id=country_id)
        #return [Indicator(**i) for i in data]
        return data