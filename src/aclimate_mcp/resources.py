"""
Resources:
    - aclimate://countries
    - aclimate://indicators/{country_id}
    - aclimate://indicator-categories
"""

from __future__ import annotations

from typing import Awaitable, Callable

from aclimatesdkpy.aclimate_client import AClimateClient
from aclimatesdkpy.aclimate_models import (
    IndicatorCategory,
    IndicatorWithFeatures,
)

from aclimate_mcp.models import CountryStations

# Lazy provider: resolves the shared client inside the running event loop.
GetClient = Callable[[], Awaitable[AClimateClient]]


def register_resources(mcp, get_client: GetClient) -> None:
    # ──────────────────────────────────────────────────────────────────────────
    # RESOURCES
    # ──────────────────────────────────────────────────────────────────────────

    @mcp.resource("aclimate://countries", mime_type="application/json")
    async def list_countries() -> list[CountryStations]:
        """Countries as actually served, with station counts.

        The upstream /countries catalogue disagrees with the station list
        (bug S3: it omits countries that have stations - e.g. El Salvador,
        the only one with indicator data - and lists countries that have
        none). The station list is therefore the primary source here; the
        catalogue only contributes entries so nothing upstream is hidden.
        """
        client = await get_client()
        locations = await client.get_locations_by_search(q="")
        by_id: dict[int, CountryStations] = {}
        for loc in locations:
            entry = by_id.get(loc.country_id)
            if entry is None:
                entry = CountryStations(
                    id=loc.country_id,
                    name=loc.country_name,
                    iso2=loc.country_iso2,
                    stations=0,
                )
                by_id[loc.country_id] = entry
            entry.stations += 1
        try:
            for country in await client.get_countries():
                if country.id not in by_id:
                    by_id[country.id] = CountryStations(
                        id=country.id, name=country.name, iso2=country.iso2, stations=0
                    )
                else:
                    by_id[country.id].name = by_id[country.id].name or country.name
                    by_id[country.id].iso2 = by_id[country.id].iso2 or country.iso2
        except Exception:  # noqa: BLE001 - the catalogue is optional enrichment
            pass
        return sorted(by_id.values(), key=lambda c: (-c.stations, c.id))

    @mcp.resource("aclimate://indicators/categories", mime_type="application/json")
    async def list_indicator_categories() -> list[IndicatorCategory]:
        """List of agroclimatic indicators categories."""
        #data = await cached_get("indicators:categories:all","/indicator-category-mng/all")
        client = await get_client()
        data = await client.get_indicators_all_categories()
        #return [IndicatorCategory(**c) for c in data]
        return data

    @mcp.resource("aclimate://indicators/{country_id}", mime_type="application/json")
    async def list_indicators(country_id: int) -> list[IndicatorWithFeatures]:
        """List of all agroclimatic indicators by country."""
        #cache_key = f"indicators:country:{country_id}"
        #data = await cached_get(cache_key,"/indicator-mng/by-country",country_id=country_id,)
        client = await get_client()
        data = await client.get_indicators_by_country(country_id=country_id)
        #return [Indicator(**i) for i in data]
        return data