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
    # ADMINISTRATIVE REGIONS AND LOCATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool(name="find_admin_region",
            description="Search for administrative regions (departments, states, municipalities) by name.")
    async def find_admin_region(name: str, level: str = "admin1") -> list[object]:
        cache_key = f"admin:{level}:name:{name.lower()}"

        if level == "admin1":
            data = await cached_get(cache_key, "/admin1/by-name", name=name)
        else:
            data = await cached_get(cache_key, "/admin2/by-name", name=name)

        if not data:
            #return f"Region not found '{name}' at {level}."
            return []

        return data

    @mcp.tool(name="find_locations",
            description="Search for climate monitoring locations by name. Always use this before querying historical data or indicators to obtain the correct location_id.")
    async def find_locations(name: str) -> list[object]:
        cache_key = f"locations:name:{name.lower()}"
        data = await cached_get(cache_key, "/locations/by-name", name=name)
        records = [Location(**loc) for loc in data]
        #return ctx.locations_summary(records)
        return records

    # ═══════════════════════════════════════════════════════════════════════════
    # HISTORICAL CLIMATE
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool(name="get_daily_climate",
            description="Search for historical daily climate data by locations and date range.")
    async def get_daily_climate(
        location_ids: str,
        start_date: str,
        end_date: str
    ) -> list[object]:
        cache_key = f"historical-daily:{location_ids}:{start_date}:{end_date}"

        data = await cached_get(
            cache_key,
            "/historical-daily/by-date-range-all-measures",
            location_ids=location_ids,
            start_date=start_date,
            end_date=end_date,
        )

        records = [ClimateHistoricalDaily(**r) for r in data]
        #return ctx.daily_climate_summary(records)
        return records

    @mcp.tool(name="get_monthly_climate",
            description="Search for historical monthly climate data by locations and date range.")
    async def get_monthly_climate(
        location_ids: str,
        start_date: str,
        end_date: str
    ) -> list[object]:
        cache_key = f"historical-monthly:{location_ids}:{start_date}:{end_date}"

        data = await cached_get(
            cache_key,
            "/historical-monthly/by-date-range-all-measures",
            location_ids=location_ids,
            start_date=start_date,
            end_date=end_date,
        )

        records = [ClimateHistoricalMonthly(**r) for r in data]
        #return ctx.monthly_climate_summary(records)
        return records

    @mcp.tool(name="get_climatology",
            description="Search for historical climatology data by locations and month range.")
    async def get_climatology(
        location_ids: str,
        start_month: int,
        end_month: int
    ) -> list[object]:
        cache_key = f"climatology:{location_ids}:{start_month}:{end_month}"

        data = await cached_get(
            cache_key,
            "/climatology/by-month-range-location-ids-all-measures",
            location_ids=location_ids,
            start_month=start_month,
            end_month=end_month,
        )

        records = [ClimateHistoricalClimatology(**r) for r in data]
        #return ctx.climatology_narrative(records)
        return records

    @mcp.tool(name="get_climate_extremes_daily",
            description="Get the first and last (extreme dates) data of daily climate for a location.")
    async def get_climate_extremes_daily(location_id: int) -> list[object]:
        data = await cached_get(
            f"minmax:daily:{location_id}",
            "/historical-daily/minmax-by-location",
            location_id=location_id,
        )
        #return ctx.minmax_daily_summary([MinMaxDailyRecord(**r) for r in data])
        records = [MinMaxDailyRecord(**r) for r in data]
        return records

    @mcp.tool(name="get_climate_extremes_monthly",
            description="Get the first and last (extreme dates) data of monthly climate for a location.")
    async def get_climate_extremes_monthly(location_id: int) -> list[object]:
        data = await cached_get(
            f"minmax:monthly:{location_id}",
            "/historical-monthly/minmax-by-location",
            location_id=location_id,
        )
        #return ctx.minmax_daily_summary([MinMaxDailyRecord(**r) for r in data])
        records = [MinMaxDailyRecord(**r) for r in data]
        return records

    @mcp.tool(name="get_climate_extremes_climatology",
            description="Get the first and last (extreme dates) data of climatology climate for a location.")
    async def get_climate_extremes_climatology(location_id: int) -> list[object]:
        data = await cached_get(
            f"minmax:climatology:{location_id}",
            "/climatology/minmax-by-location",
            location_id=location_id,
        )
        #return ctx.minmax_climatology_summary([MinMaxClimatologyRecord(**r) for r in data])
        records = [MinMaxClimatologyRecord(**r) for r in data]
        return records

    # ═══════════════════════════════════════════════════════════════════════════
    # INDICATORS
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool(name="get_indicator_history",
            description="Get the historical data of indicators for a location.")
    async def get_indicator_history(location_id: int) -> list[object]:
        data = await cached_get(
            f"indicators:history:{location_id}",
            "/indicator/by-location-id",
            location_id=location_id,
        )
        records = [ClimateHistoricalIndicatorRecord(**r) for r in data]
        #return ctx.indicator_narrative([ClimateHistoricalIndicatorRecord(**r) for r in data])
        return records


    @mcp.tool(name="get_indicator_extremes",
            description="Get the first and last (extreme dates) data of a indicator for a location.")
    async def get_indicator_extremes(location_id: int) -> list[object]:
        data = await cached_get(
            f"minmax:indicators:{location_id}",
            "/indicator/minmax-by-location",
            location_id=location_id,
        )
        #return ctx.indicator_extremes_narrative([MinMaxIndicatorRecord(**r) for r in data])
        records = [MinMaxIndicatorRecord(**r) for r in data]
        return records

    @mcp.tool(name="get_features_indicator",
            description="Get the features of an indicator for a specific location.")
    async def get_features_indicator(
        indicator_id: int,
        country_id: int,
        feature_type: str = "recommendation",
    ) -> list[object]:
        data = await cached_get(
            f"features:{indicator_id}:{country_id}",
            "/indicator-features/by-indicator-and-country",
            indicator_id=indicator_id,
            country_id=country_id,
            type=feature_type,
        )
        #return ctx.recommendations_narrative([IndicatorFeature(**f) for f in data])
        records = [IndicatorFeature(**f) for f in data]
        return records

    # ═══════════════════════════════════════════════════════════════════════════
    # SPATIAL DATA
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def get_point_data_from_coordinates(
        lat: float,
        lon: float,
        workspace: str,
        store: str,
        start_date: str,
        end_date: str,
        temporality: str = "monthly",
    ) -> list[object]:
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
