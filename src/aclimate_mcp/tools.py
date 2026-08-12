from __future__ import annotations

from typing import Any, Awaitable, Callable

from aclimatesdkpy import AClimateClient
from aclimatesdkpy.aclimate_models import (
    ClimateHistoricalIndicatorRecord,
    IndicatorFeature,
    Location,
)

#CachedGet = Callable[..., Awaitable[Any]]
#GetClient = Callable[..., Awaitable[Any]]


#def register_tools(mcp, cached_get: CachedGet, ctx, get_client: GetClient) -> None:
def register_tools(mcp, client: AClimateClient) -> None:
    # ═══════════════════════════════════════════════════════════════════════════
    # ADMINISTRATIVE REGIONS AND LOCATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool(name="find_administrative_region_level_1",
            description="Search for administrative regions level 2 (departments, states) by name.")
    async def find_administrative_region_level_1(name: str) -> list[object]:
        #cache_key = f"admin:{level}:name:{name.lower()}"
        data = await client.get_admin1_by_name(name)

        if not data:
            #return f"Region not found '{name}' at {level}."
            return []

        return data

    @mcp.tool(name="find_administrative_region_level_2",
            description="Search for administrative regions level 1 (municipalities, counties) by name.")
    async def find_administrative_region_level_2(name: str) -> list[object]:
            #cache_key = f"admin:{level}:name:{name.lower()}"
            data = await client.get_admin2_by_name(name)
    
            if not data:
                #return f"Region not found '{name}' at {level}."
                return []
    
            return data

    @mcp.tool(name="search_locations_by_name",
            description="Get a list of locations available by name. Always use this before querying historical data or indicators to obtain the correct location_id.")
    async def search_locations_by_name(name: str) -> list[object]:
        #cache_key = f"locations:name:{name.lower()}"
        #data = await cached_get(cache_key, "/locations/by-name", name=name)
        data = await client.get_locations_by_search(name=name)
        #records = [Location(**loc) for loc in data]
        #return ctx.locations_summary(records)
        #return records
        return data

    # ═══════════════════════════════════════════════════════════════════════════
    # HISTORICAL CLIMATE
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool(name="get_daily_climate",
            description="Search for historical daily climate data by locations and date range.")
    async def get_daily_climate(location_ids: list[int],start_date: str,end_date: str) -> list[object]:
        #cache_key = f"historical-daily:{location_ids}:{start_date}:{end_date}"

        #data = await cached_get(cache_key,"/historical-daily/by-date-range-all-measures",location_ids=location_ids,start_date=start_date,end_date=end_date,)
        data = await client.get_historical_daily_by_date_range_all_measures(
            location_ids=",".join(map(str, location_ids)),
            start_date=start_date,
            end_date=end_date
        )
        #records = [ClimateHistoricalDaily(**r) for r in data]
        #return ctx.daily_climate_summary(records)
        #return records
        return data

    @mcp.tool(name="get_monthly_climate",
            description="Search for historical monthly climate data by locations and date range.")
    async def get_monthly_climate(location_ids: list[int],start_date: str,end_date: str) -> list[object]:
        #cache_key = f"historical-monthly:{location_ids}:{start_date}:{end_date}"

        #data = await cached_get(cache_key,"/historical-monthly/by-date-range-all-measures",location_ids=location_ids,start_date=start_date,end_date=end_date,)
        data = await client.get_historical_monthly_by_date_range_all_measures(
            location_ids=",".join(map(str, location_ids)),
            start_date=start_date,
            end_date=end_date
        )

        #records = [ClimateHistoricalMonthly(**r) for r in data]
        #return ctx.monthly_climate_summary(records)
        #return records
        return data

    @mcp.tool(name="get_climatology",
            description="Search for historical climatology data by locations and month range.")
    async def get_climatology(location_ids: list[int],start_month: int,end_month: int) -> list[object]:
        #cache_key = f"climatology:{location_ids}:{start_month}:{end_month}"

        #data = await cached_get(cache_key,"/climatology/by-month-range-location-ids-all-measures",location_ids=location_ids,start_month=start_month,end_month=end_month,)
        data = await client.get_climatology_by_month_range_location_ids_all_measures(
            location_ids=",".join(map(str, location_ids)),
            start_month=start_month,
            end_month=end_month
        )

        #records = [ClimateHistoricalClimatology(**r) for r in data]
        #return ctx.climatology_narrative(records)
        #return records
        return data

    @mcp.tool(name="get_available_climate_daliy_date_ranges",
            description="Returns the available date ranges for querying climate daily data for one location. Use this tool before requesting historical climate information to determine the valid start and end dates supported by the data source.")
    async def get_available_climate_daliy_date_ranges(location_id: int) -> list[object]:
        #data = await cached_get(f"minmax:daily:{location_id}","/historical-daily/minmax-by-location",location_id=location_id,)
        data = await client.get_historical_daily_minmax_by_location(location_id=location_id)
        #return ctx.minmax_daily_summary([MinMaxDailyRecord(**r) for r in data])
        #records = [MinMaxDailyRecord(**r) for r in data]
        #return records
        return data

    @mcp.tool(name="get_available_climate_monthly_date_ranges",
            description="Returns the available date ranges for querying climate monthly data for one location. Use this tool before requesting historical climate information to determine the valid start and end dates supported by the data source.")
    async def get_available_climate_monthly_date_ranges(location_id: int) -> list[object]:
        #data = await cached_get(f"minmax:monthly:{location_id}","/historical-monthly/minmax-by-location",location_id=location_id,)
        data = await client.get_historical_monthly_minmax_by_location(location_id=location_id)
        #return ctx.minmax_daily_summary([MinMaxDailyRecord(**r) for r in data])
        #records = [MinMaxDailyRecord(**r) for r in data]
        #return records
        return data

    @mcp.tool(name="get_available_climate_climatology_date_ranges",
            description="Returns the available date ranges for querying climatology data for one location. Use this tool before requesting historical climate information to determine the valid start and end dates supported by the data source.")
    async def get_available_climate_climatology_date_ranges(location_id: int) -> list[object]:
        #data = await cached_get(f"minmax:climatology:{location_id}","/climatology/minmax-by-location",location_id=location_id,)
        data = await client.get_climatology_minmax_by_location(location_id=location_id)
        #return ctx.minmax_climatology_summary([MinMaxClimatologyRecord(**r) for r in data])
        #records = [MinMaxClimatologyRecord(**r) for r in data]
        #return records
        return data

    # ═══════════════════════════════════════════════════════════════════════════
    # INDICATORS
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool(name="get_indicator_history",
            description="Get the historical data of indicators for a location.")
    async def get_indicator_history(location_id: int) -> list[object]:
        #data = await cached_get(f"indicators:history:{location_id}","/indicator/by-location-id",location_id=location_id,)
        data = await client.get_indicator_by_location_id(location_id=location_id)
        #records = [ClimateHistoricalIndicatorRecord(**r) for r in data]
        #return ctx.indicator_narrative([ClimateHistoricalIndicatorRecord(**r) for r in data])
        #return records
        return data

    @mcp.tool(name="get_available_indicator_date_ranges",
            description="Returns the available date ranges for querying indicators data for one location. Use this tool before requesting indicator information to determine the valid start and end dates supported by the data source.")
    async def get_available_indicator_date_ranges(location_id: int) -> list[object]:
        #data = await cached_get(f"minmax:indicators:{location_id}","/indicator/minmax-by-location",location_id=location_id,)
        data = await client.get_indicator_minmax_by_location(location_id=location_id)
        #return ctx.indicator_extremes_narrative([MinMaxIndicatorRecord(**r) for r in data])
        #records = [MinMaxIndicatorRecord(**r) for r in data]
        #return records
        return data

    @mcp.tool(name="get_features_indicator",
            description="Get the features of an indicator for a specific location.")
    async def get_features_indicator(indicator_id: int,country_id: int,feature_type: str = "recommendation",) -> list[object]:
        #data = await cached_get(f"features:{indicator_id}:{country_id}","/indicator-features/by-indicator-and-country",indicator_id=indicator_id,country_id=country_id,type=feature_type,)
        data = await client.get_indicator_features_by_indicator_and_country(
            indicator_id=indicator_id,
            country_id=country_id,
            type=feature_type
        )
        #return ctx.recommendations_narrative([IndicatorFeature(**f) for f in data])
        #records = [IndicatorFeature(**f) for f in data]
        #return records
        return data

    # ═══════════════════════════════════════════════════════════════════════════
    # SPATIAL DATA
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool(name="get_point_data_from_coordinates",
            description="Get point data from coordinates.")
    async def get_point_data_from_coordinates(lat: float,lon: float,workspace: str,store: str,start_date: str,end_date: str,temporality: str = "monthly",) -> list[object]:
        #cache_key = f"point-data:{lat}:{lon}:{workspace}:{store}:{start_date}:{end_date}:{temporality}"
        #data = await cached_get(cache_key,"/spatial/point-data-by-coordinates",lat=lat,lon=lon,workspace=workspace,store=store,start_date=start_date,end_date=end_date,temporality=temporality,)
        data = await client.get_spatial_point_data_by_coordinates(
            lat=lat,
            lon=lon,
            workspace=workspace,
            store=store,
            start_date=start_date,
            end_date=end_date,
            temporality=temporality
        )
        #return ctx.point_data_summary(data)
        return data
