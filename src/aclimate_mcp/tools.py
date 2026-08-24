from __future__ import annotations

import functools
from datetime import date
from typing import Awaitable, Callable, Literal

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from aclimatesdkpy import AClimateClient
from aclimatesdkpy.aclimate_api_error import AClimateAPIError
from aclimatesdkpy.aclimate_auth_error import AClimateAuthError
from aclimatesdkpy.aclimate_models import (
    Admin1,
    Admin2,
    ClimateHistoricalDateRecord,
    ClimateHistoricalMonthRecord,
    ClimateHistoricalIndicatorRecord,
    IndicatorFeature,
    Location,
    MinMaxDateRecord,
    MinMaxMonthRecord,
    PointDataRequest,
    PointDataResponse,
)
from aclimatesdkpy.context_builder import ContextBuilder

# Lazy provider: resolves the shared client inside the running event loop.
GetClient = Callable[[], Awaitable[AClimateClient]]

# Raw time-series responses are capped so a single tool call cannot flood the
# agent's context window (one year of daily data for one location is ~74k
# tokens as raw JSON; the summary of the same data is ~170 tokens).
RAW_RECORD_LIMIT = 500

Detail = Literal["summary", "raw"]

_DETAIL_HINT = (
    " Set detail='summary' (default) for a compact statistical narrative, or "
    "detail='raw' for the full records (rejected above "
    f"{RAW_RECORD_LIMIT} records — narrow the range or use the summary)."
)


# ── ERROR TRANSLATION ─────────────────────────────────────────────────────────
# The SDK raises transport/auth/API errors that mean nothing to the calling
# agent. Translate them into messages that say what to do next, and never
# forward auth details (they could echo server credentials back to the caller).
def _tool_errors(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ToolError:
            raise
        except AClimateAuthError as exc:
            raise ToolError(
                "The AClimate MCP server could not authenticate against the "
                "AClimate API. This is a server-side configuration problem "
                "(ACLIMATE_CLIENT_ID / ACLIMATE_CLIENT_SECRET); it cannot be "
                "fixed from this conversation. Report it to the operator."
            ) from exc
        except AClimateAPIError as exc:
            if exc.status_code == 404:
                raise ToolError(
                    "The AClimate API has no data for these parameters. Check "
                    "the location_id with search_locations_by_name and the "
                    "valid ranges with the get_available_* tools, then retry."
                ) from exc
            if exc.status_code >= 500:
                raise ToolError(
                    f"The AClimate API failed with a server error "
                    f"({exc.status_code}). This is usually transient — retry "
                    "once; if it persists, the service is down."
                ) from exc
            raise ToolError(
                f"The AClimate API rejected the request: {exc}. "
                "Review the parameters and retry."
            ) from exc
        except httpx.TransportError as exc:
            raise ToolError(
                "Could not reach the AClimate API (network error or timeout). "
                "This is usually transient — retry once; if it persists, the "
                "service is unreachable."
            ) from exc

    return wrapper


# ── INPUT VALIDATION ──────────────────────────────────────────────────────────
# Reject malformed parameters before spending an API round trip, with messages
# that say exactly what to send instead.
def _iso_date(value: str, field: str) -> date:
    # Canonical YYYY-MM-DD only. fromisoformat() alone is not enough: Python
    # 3.11+ also accepts compact forms like "20240101" that 3.10 rejects and
    # that would travel verbatim to the API.
    try:
        parsed = date.fromisoformat(value)
        if value != parsed.isoformat():
            raise ValueError
        return parsed
    except ValueError:
        raise ToolError(
            f"{field} must be an ISO date in YYYY-MM-DD format, got {value!r}."
        ) from None


def _validate_date_range(start_date: str, end_date: str) -> None:
    start = _iso_date(start_date, "start_date")
    end = _iso_date(end_date, "end_date")
    if start > end:
        raise ToolError(
            f"start_date ({start_date}) is after end_date ({end_date}). "
            "Swap them or fix the range."
        )


def _validate_month(value: int, field: str) -> None:
    if not 1 <= value <= 12:
        raise ToolError(f"{field} must be a month between 1 and 12, got {value}.")


def _cap_raw(records: list, tool: str) -> list:
    if len(records) > RAW_RECORD_LIMIT:
        raise ToolError(
            f"{tool} returned {len(records)} records, above the raw limit of "
            f"{RAW_RECORD_LIMIT}. Narrow the date range or locations, or call "
            "again with detail='summary'."
        )
    return records


def register_tools(mcp, get_client: GetClient, ctx: ContextBuilder) -> None:
    # ═══════════════════════════════════════════════════════════════════════════
    # ADMINISTRATIVE REGIONS AND LOCATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    """
    @mcp.tool(name="find_administrative_region_level_1",
            description="Search for administrative regions level 1 (departments, states) by name.")
    @_tool_errors
    async def find_administrative_region_level_1(name: str) -> list[Admin1]:
        client = await get_client()
        return await client.get_admin1_by_name(name)

    @mcp.tool(name="find_administrative_region_level_2",
            description="Search for administrative regions level 2 (municipalities, counties) by name.")
    @_tool_errors
    async def find_administrative_region_level_2(name: str) -> list[Admin2]:
        client = await get_client()
        return await client.get_admin2_by_name(name)

    """
    
    @mcp.tool(name="search_locations_by_name",
            description="Search monitoring locations by name. Always use this first: every climate and indicator tool needs the location_id values this returns.")
    @_tool_errors
    async def search_locations_by_name(name: str) -> list[Location]:
        client = await get_client()
        return await client.get_locations_by_search(q=name)

    # ═══════════════════════════════════════════════════════════════════════════
    # HISTORICAL CLIMATE
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool(name="get_daily_climate",
            description="Historical daily climate data (precipitation, temperatures, solar radiation) for one or more locations over a date range. Dates are ISO YYYY-MM-DD; check valid ranges first with get_available_climate_daily_date_ranges." + _DETAIL_HINT)
    @_tool_errors
    async def get_daily_climate(
        location_ids: list[int],
        start_date: str,
        end_date: str,
        detail: Detail = "summary",
    ) -> str | list[ClimateHistoricalDateRecord]:
        _validate_date_range(start_date, end_date)
        client = await get_client()
        data = await client.get_historical_daily_by_date_range_all_measures(
            location_ids="[" + ",".join(map(str, location_ids)) + "]",
            start_date=start_date,
            end_date=end_date,
        )
        if detail == "raw":
            return _cap_raw(data, "get_daily_climate")
        return ctx.daily_climate_summary(data)

    @mcp.tool(name="get_monthly_climate",
            description="Historical monthly climate data for one or more locations over a date range. Dates are ISO YYYY-MM-DD; check valid ranges first with get_available_climate_monthly_date_ranges." + _DETAIL_HINT)
    @_tool_errors
    async def get_monthly_climate(
        location_ids: list[int],
        start_date: str,
        end_date: str,
        detail: Detail = "summary",
    ) -> str | list[ClimateHistoricalDateRecord]:
        _validate_date_range(start_date, end_date)
        client = await get_client()
        data = await client.get_historical_monthly_by_date_range_all_measures(
            location_ids="[" + ",".join(map(str, location_ids)) + "]",
            start_date=start_date,
            end_date=end_date,
        )
        if detail == "raw":
            return _cap_raw(data, "get_monthly_climate")
        return ctx.monthly_climate_summary(data)

    @mcp.tool(name="get_climatology",
            description="Historical climate normals (long-term monthly averages) for one or more locations over a month range. Months are 1-12." + _DETAIL_HINT)
    @_tool_errors
    async def get_climatology(
        location_ids: list[int],
        start_month: int,
        end_month: int,
        detail: Detail = "summary",
    ) -> str | list[ClimateHistoricalMonthRecord]:
        _validate_month(start_month, "start_month")
        _validate_month(end_month, "end_month")
        client = await get_client()
        data = await client.get_climatology_by_month_range_location_ids_all_measures(
            location_ids="[" + ",".join(map(str, location_ids)) + "]",
            start_month=start_month,
            end_month=end_month,
        )
        if detail == "raw":
            return _cap_raw(data, "get_climatology")
        return ctx.climatology_narrative(data)

    @mcp.tool(name="get_available_climate_daily_date_ranges",
            description="Available date range for daily climate data at one location. Call this before get_daily_climate to pick valid start and end dates.")
    @_tool_errors
    async def get_available_climate_daily_date_ranges(location_id: int) -> list[MinMaxDateRecord]:
        client = await get_client()
        return await client.get_historical_daily_minmax_by_location(location_id=location_id)

    @mcp.tool(name="get_available_climate_monthly_date_ranges",
            description="Available date range for monthly climate data at one location. Call this before get_monthly_climate to pick valid start and end dates.")
    @_tool_errors
    async def get_available_climate_monthly_date_ranges(location_id: int) -> list[MinMaxDateRecord]:
        client = await get_client()
        return await client.get_historical_monthly_minmax_by_location(location_id=location_id)

    @mcp.tool(name="get_available_climate_climatology_date_ranges",
            description="Available month range for climatology data at one location. Call this before get_climatology.")
    @_tool_errors
    async def get_available_climate_climatology_date_ranges(location_id: int) -> list[MinMaxMonthRecord]:
        client = await get_client()
        return await client.get_climatology_minmax_by_location(location_id=location_id)

    # ═══════════════════════════════════════════════════════════════════════════
    # INDICATORS
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool(name="get_indicator_history",
            description="Historical values of agroclimatic indicators for one location. Check valid ranges first with get_available_indicator_date_ranges." + _DETAIL_HINT)
    @_tool_errors
    async def get_indicator_history(
        location_id: int,
        detail: Detail = "summary",
    ) -> str | list[ClimateHistoricalIndicatorRecord]:
        client = await get_client()
        data = await client.get_indicator_by_location_id(location_id=location_id)
        if detail == "raw":
            return _cap_raw(data, "get_indicator_history")
        return ctx.indicator_narrative(data)

    @mcp.tool(name="get_available_indicator_date_ranges",
            description="Available date range for indicator data at one location. Call this before get_indicator_history.")
    @_tool_errors
    async def get_available_indicator_date_ranges(location_id: int) -> list[MinMaxDateRecord]:
        client = await get_client()
        return await client.get_indicator_minmax_by_location(location_id=location_id)

    @mcp.tool(name="get_features_indicator",
            description="Features or recommendations attached to one indicator in one country. Get indicator_id from the aclimate://indicators/{country_id} resource and country_id from aclimate://countries. feature_type is 'recommendation' or 'feature'.")
    @_tool_errors
    async def get_features_indicator(
        indicator_id: int,
        country_id: int,
        feature_type: str = "recommendation",
    ) -> list[IndicatorFeature]:
        client = await get_client()
        return await client.get_indicator_features_by_indicator_and_country(
            indicator_id=indicator_id,
            country_id=country_id,
            type=feature_type,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # SPATIAL DATA
    # ═══════════════════════════════════════════════════════════════════════════

    @mcp.tool(name="get_point_data_from_coordinates",
            description="Raster time series for a geographic point (latitude/longitude) from a GeoServer workspace and store. Requires knowing the workspace and store names in advance. Dates are ISO YYYY-MM-DD.")
    @_tool_errors
    async def get_point_data_from_coordinates(
        lat: float,
        lon: float,
        workspace: str,
        store: str,
        start_date: str,
        end_date: str,
        temporality: Literal["daily", "monthly", "annual"] = "monthly",
    ) -> PointDataResponse:
        _validate_date_range(start_date, end_date)
        client = await get_client()
        # The API expects a POST body with coordinates as [longitude, latitude] pairs.
        request = PointDataRequest(
            coordinates=[[lon, lat]],
            workspace=workspace,
            store=store,
            start_date=start_date,  # type: ignore[arg-type]  # pydantic coerces ISO str -> date
            end_date=end_date,  # type: ignore[arg-type]
            temporality=temporality,
        )
        return await client.post_geoserver_point_data(request)
