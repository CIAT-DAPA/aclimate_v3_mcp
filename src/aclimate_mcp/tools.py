from __future__ import annotations

from typing import Any, Awaitable, Callable

from aclimate_sdk.aclimate_models import (
    ClimateHistoricalClimatology,
    ClimateHistoricalDaily,
    ClimateHistoricalIndicatorRecord,
    ClimateHistoricalMonthly,
    IndicatorFeature,
    Location,
    MinMaxClimatologyRecord,
    MinMaxDailyRecord,
    MinMaxIndicatorRecord,
)

CachedGet = Callable[..., Awaitable[Any]]
GetClient = Callable[..., Awaitable[Any]]


def register_tools(mcp, cached_get: CachedGet, ctx, get_client: GetClient) -> None:
    # ═══════════════════════════════════════════════════════════════════════════
    # GEO
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def find_admin_region(name: str, level: str = "admin1") -> str:
        cache_key = f"admin:{level}:name:{name.lower()}"

        if level == "admin1":
            data = await cached_get(cache_key, "/admin1/by-name", name=name)
        else:
            data = await cached_get(cache_key, "/admin2/by-name", name=name)

        if not data:
            return f"No se encontró ninguna región '{name}' en el nivel {level}."

        lines = [f"Regiones encontradas para '{name}' (nivel {level}):"]
        for item in data:
            lines.append(
                f"  • [{item.get('id')}] {item.get('name')}"
                f" — {item.get('country_name', '')} (ext_id={item.get('ext_id', '?')})"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def find_locations(name: str) -> str:
        cache_key = f"locations:name:{name.lower()}"
        data = await cached_get(cache_key, "/locations/by-name", name=name)
        locations = [Location(**loc) for loc in data]
        return ctx.locations_summary(locations)

    @mcp.tool()
    async def get_locations_with_current_data(country_id: int, days: int = 7) -> str:
        cache_key = f"locations-data:country:{country_id}:days:{days}"
        data = await cached_get(
            cache_key,
            "/locations/by-country-ids-with-data",
            country_ids=country_id,
            days=days,
        )
        return ctx.current_conditions_summary(data)

    @mcp.tool()
    async def get_point_data_from_coordinates(
        lat: float,
        lon: float,
        workspace: str,
        store: str,
        start_date: str,
        end_date: str,
        temporality: str = "monthly",
    ) -> str:
        client = await get_client()
        data = await client.post(
            "/geoserver/point-data",
            json_body={
                "coordinates": [[lon, lat]],
                "start_date": start_date,
                "end_date": end_date,
                "workspace": workspace,
                "store": store,
                "temporality": temporality,
            },
        )
        return (
            f"Datos raster para ({lat}, {lon}) — {workspace}/{store} "
            f"[{start_date} → {end_date}]:\n{data}"
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # HISTORICAL CLIMATE
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def get_daily_climate(
        location_ids: str,
        start_date: str,
        end_date: str,
        measures: str | None = None,
    ) -> str:
        cache_key = f"historical-daily:{location_ids}:{start_date}:{end_date}:{measures}"

        endpoint = (
            "/historical-daily/by-date-range-and-specific-measures"
            if measures
            else "/historical-daily/by-date-range-all-measures"
        )

        data = await cached_get(
            cache_key,
            endpoint,
            location_ids=location_ids,
            measures=measures,
            start_date=start_date,
            end_date=end_date,
        )

        records = [ClimateHistoricalDaily(**r) for r in data]
        return ctx.daily_climate_summary(records)

    @mcp.tool()
    async def get_monthly_climate(
        location_ids: str,
        start_date: str,
        end_date: str,
        measures: str | None = None,
    ) -> str:
        cache_key = f"historical-monthly:{location_ids}:{start_date}:{end_date}:{measures}"

        endpoint = (
            "/historical-monthly/by-date-range-and-specific-measures"
            if measures
            else "/historical-monthly/by-date-range-all-measures"
        )

        data = await cached_get(
            cache_key,
            endpoint,
            location_ids=location_ids,
            measures=measures,
            start_date=start_date,
            end_date=end_date,
        )

        records = [ClimateHistoricalMonthly(**r) for r in data]
        return ctx.monthly_climate_summary(records)

    @mcp.tool()
    async def get_climatology(
        location_ids: str,
        start_month: int,
        end_month: int,
        measures: str | None = None,
    ) -> str:
        cache_key = f"climatology:{location_ids}:{start_month}:{end_month}:{measures}"

        endpoint = (
            "/climatology/by-month-range-location-ids-and-specific-measures"
            if measures
            else "/climatology/by-month-range-location-ids-all-measures"
        )

        data = await cached_get(
            cache_key,
            endpoint,
            location_ids=location_ids,
            measures=measures,
            start_month=start_month,
            end_month=end_month,
        )

        records = [ClimateHistoricalClimatology(**r) for r in data]
        return ctx.climatology_narrative(records)

    @mcp.tool()
    async def get_climate_extremes_daily(location_id: int) -> str:
        data = await cached_get(
            f"minmax:daily:{location_id}",
            "/historical-daily/minmax-by-location",
            location_id=location_id,
        )
        return ctx.minmax_daily_summary([MinMaxDailyRecord(**r) for r in data])

    @mcp.tool()
    async def get_climate_extremes_climatology(location_id: int) -> str:
        data = await cached_get(
            f"minmax:climatology:{location_id}",
            "/climatology/minmax-by-location",
            location_id=location_id,
        )
        return ctx.minmax_climatology_summary(
            [MinMaxClimatologyRecord(**r) for r in data]
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # INDICATORS
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def list_indicators_by_country(
        country_id: int,
        indicator_type: str = "CLIMATE",
        temporality: str | None = None,
    ) -> str:
        data = await cached_get(
            f"indicators:country:{country_id}:{indicator_type}:{temporality}",
            "/indicator-mng/by-country",
            country_id=country_id,
            type=indicator_type,
            temporality=temporality,
        )
        return ctx.indicators_catalog_summary(data)

    @mcp.tool()
    async def get_indicator_history(location_id: int) -> str:
        data = await cached_get(
            f"indicators:history:{location_id}",
            "/indicator/by-location-id",
            location_id=location_id,
        )
        return ctx.indicator_narrative(
            [ClimateHistoricalIndicatorRecord(**r) for r in data]
        )

    @mcp.tool()
    async def get_indicator_by_name_and_location(
        location_name: str,
        indicator_name: str,
    ) -> str:
        data = await cached_get(
            f"indicators:{indicator_name}:{location_name}",
            "/indicator/by-location-and-indicator-name",
            location_name=location_name,
            indicator_name=indicator_name,
        )
        return ctx.indicator_narrative(
            [ClimateHistoricalIndicatorRecord(**r) for r in data],
            indicator_name,
        )

    @mcp.tool()
    async def get_indicator_extremes(location_id: int) -> str:
        data = await cached_get(
            f"minmax:indicators:{location_id}",
            "/indicator/minmax-by-location",
            location_id=location_id,
        )
        return ctx.indicator_extremes_narrative(
            [MinMaxIndicatorRecord(**r) for r in data]
        )

    @mcp.tool()
    async def get_agro_recommendations(
        indicator_id: int,
        country_id: int,
        feature_type: str = "recommendation",
    ) -> str:
        data = await cached_get(
            f"features:{indicator_id}:{country_id}",
            "/indicator-features/by-indicator-and-country",
            indicator_id=indicator_id,
            country_id=country_id,
            type=feature_type,
        )
        return ctx.recommendations_narrative(
            [IndicatorFeature(**f) for f in data]
        )