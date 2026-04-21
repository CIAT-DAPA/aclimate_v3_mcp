from __future__ import annotations

from typing import Any, Awaitable, Callable

from aclimate_sdk.aclimate_models import (
    Country,
    Indicator,
    IndicatorCategory,
)

# Firma del helper que viene desde server
CachedGet = Callable[..., Awaitable[Any]]

def register_resources(mcp, cached_get: CachedGet) -> None:
    # ──────────────────────────────────────────────────────────────────────────
    # RESOURCES
    # ──────────────────────────────────────────────────────────────────────────

    @mcp.resource("aclimate://countries", mime_type="application/json")
    async def list_countries() -> list[Country]:
        """List all countries in AClimate."""
        data = await cached_get("countries:all", "/countries")
        return [Country(**c) for c in data]

    @mcp.resource("aclimate://indicator-categories", mime_type="application/json")
    async def list_indicator_categories() -> list[IndicatorCategory]:
        """List of agroclimatic indicators categories."""
        data = await cached_get(
            "indicators:categories:all",
            "/indicator-category-mng/all",
        )
        return [IndicatorCategory(**c) for c in data]

    @mcp.resource("aclimate://indicators/{country_id}", mime_type="application/json")
    async def list_indicators(country_id: int) -> list[Indicator]:
        """List of all agroclimatic indicators by country."""
        cache_key = f"indicators:country:{country_id}:CLIMATE:None"
        data = await cached_get(
            cache_key,
            "/indicator-mng/by-country",
            country_id=country_id,
        )
        return [Indicator(**i) for i in data]