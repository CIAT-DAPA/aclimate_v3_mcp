"""
Integration tests for the tool layer.

Unlike test_server.py, these use a REAL FastMCP instance and go through
mcp.call_tool(), so they exercise argument validation, the SDK call
signatures, the summary/raw detail switch and the error translation. This is
the layer that catches "that SDK method does not take this keyword" — the
class of bug unit tests with a mocked FastMCP cannot see.
"""

import asyncio
import datetime

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from aclimatesdkpy.aclimate_api_error import AClimateAPIError
from aclimatesdkpy.aclimate_auth_error import AClimateAuthError
from aclimatesdkpy.aclimate_models import ClimateHistoricalDateRecord
from aclimatesdkpy.context_builder import ContextBuilder

from aclimate_mcp.tools import RAW_RECORD_LIMIT, register_tools


def make_daily_records(count, location_id=4):
    return [
        ClimateHistoricalDateRecord(
            id=i,
            location_id=location_id,
            location_name="Palmira",
            measure_id=1,
            measure_name="Precipitation",
            measure_short_name="prec",
            measure_unit="mm",
            date=datetime.date(2024, 1, 1) + datetime.timedelta(days=i % 365),
            value=float(i % 40),
        )
        for i in range(count)
    ]


class FakeClient:
    """Records the arguments each SDK method was called with."""

    def __init__(self):
        self.calls = []
        self.daily_response = make_daily_records(10)
        self.raise_on_call = None

    def _record(self, entry):
        if self.raise_on_call is not None:
            raise self.raise_on_call
        self.calls.append(entry)

    async def get_admin1_by_name(self, name):
        self._record(("admin1", name))
        return []

    async def get_locations_by_search(self, q):
        self._record(("search", q))
        return []

    async def get_historical_daily_by_date_range_all_measures(self, location_ids, start_date, end_date):
        self._record(("daily", location_ids, start_date, end_date))
        return self.daily_response

    async def get_climatology_by_month_range_location_ids_all_measures(self, location_ids, start_month, end_month):
        self._record(("climatology", location_ids, start_month, end_month))
        return []

    async def get_historical_daily_minmax_by_location(self, location_id):
        self._record(("minmax_daily", location_id))
        from aclimatesdkpy.aclimate_models import MinMaxDateRecord

        return [
            MinMaxDateRecord(
                id=1, name="prec", location_id=location_id, location_name="Palmira",
                min_value=0.0, min_date=datetime.datetime(2010, 1, 1),
                max_value=40.0, max_date=datetime.datetime(2024, 12, 31),
            )
        ]

    async def get_indicator_by_location_id(self, location_id):
        self._record(("indicator_history", location_id))
        from aclimatesdkpy.aclimate_models import ClimateHistoricalIndicatorRecord

        return [
            ClimateHistoricalIndicatorRecord(
                id=1, indicator_id=9, indicator_name="NDD", indicator_unit="days",
                location_id=location_id, location_name="Palmira", value=3.5,
                period="monthly", start_date=datetime.datetime(2024, 1, 1),
                end_date=datetime.datetime(2024, 1, 31),
            )
        ]

    async def post_geoserver_point_data(self, request):
        self._record(("point_data", request.model_dump(mode="json")))
        from aclimatesdkpy.aclimate_models import PointDataResponse

        return PointDataResponse(total_results=0, data=[])


@pytest.fixture
def harness():
    client = FakeClient()

    async def get_client():
        return client

    mcp = FastMCP("test-aclimate")
    register_tools(mcp=mcp, get_client=get_client, ctx=ContextBuilder("es"))
    return mcp, client


def call(mcp, name, args):
    return asyncio.run(mcp.call_tool(name, args))


def text_of(result):
    content = result[0] if isinstance(result, tuple) else result.content
    return content[0].text


# ── registration and naming ───────────────────────────────────────────────────

def test_expected_tools_register(harness):
    mcp, _ = harness
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert "get_daily_climate" in names
    assert "get_available_climate_daily_date_ranges" in names, (
        "the misspelled 'daliy' tool name must stay fixed"
    )
    assert "get_available_climate_daliy_date_ranges" not in names


def test_admin_level_descriptions_are_not_swapped(harness):
    mcp, _ = harness
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    assert "departments" in tools["find_administrative_region_level_1"].description
    assert "municipalities" in tools["find_administrative_region_level_2"].description


# ── SDK call signatures ───────────────────────────────────────────────────────

def test_search_locations_passes_q_not_name(harness):
    """The SDK signature is get_locations_by_search(q=...), not name=..."""
    mcp, client = harness
    call(mcp, "search_locations_by_name", {"name": "Palmira"})
    assert client.calls[-1] == ("search", "Palmira")


def test_point_data_posts_a_request_body_with_lon_lat_order(harness):
    """The API takes a POST body; coordinates are [longitude, latitude]."""
    mcp, client = harness
    call(
        mcp,
        "get_point_data_from_coordinates",
        {
            "lat": 3.54,
            "lon": -76.30,
            "workspace": "climate",
            "store": "chirps",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
        },
    )
    kind, body = client.calls[-1]
    assert kind == "point_data"
    assert body["coordinates"] == [[-76.30, 3.54]]


def test_location_ids_schema_is_strict(harness):
    """A bare int where list[int] is expected must be rejected, not coerced."""
    mcp, _ = harness
    with pytest.raises(Exception):
        call(
            mcp,
            "get_daily_climate",
            {"location_ids": 4, "start_date": "2024-01-01", "end_date": "2024-03-31"},
        )


# ── detail: summary vs raw ────────────────────────────────────────────────────

def test_summary_is_the_default_and_returns_a_narrative(harness):
    mcp, client = harness
    result = call(
        mcp,
        "get_daily_climate",
        {"location_ids": [4], "start_date": "2024-01-01", "end_date": "2024-03-31"},
    )
    text = text_of(result)
    assert "Palmira" in text
    assert len(text) < 2000, "the summary must be compact, not the raw records"
    assert client.calls[-1] == ("daily", "4", "2024-01-01", "2024-03-31")


def test_raw_returns_records_when_under_the_cap(harness):
    mcp, client = harness
    client.daily_response = make_daily_records(10)
    result = call(
        mcp,
        "get_daily_climate",
        {
            "location_ids": [4],
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "detail": "raw",
        },
    )
    assert "Precipitation" in text_of(result)


def test_raw_above_the_cap_is_rejected_with_guidance(harness):
    mcp, client = harness
    client.daily_response = make_daily_records(RAW_RECORD_LIMIT + 1)
    with pytest.raises(ToolError, match="summary"):
        asyncio.run(
            mcp.call_tool(
                "get_daily_climate",
                {
                    "location_ids": [4],
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "detail": "raw",
                },
            )
        )


# ── input validation ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["01/03/2024", "2024-13-01", "ayer", "20240101"])
def test_invalid_dates_are_rejected_before_the_api_call(harness, bad):
    mcp, client = harness
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        asyncio.run(
            mcp.call_tool(
                "get_daily_climate",
                {"location_ids": [4], "start_date": bad, "end_date": "2024-03-31"},
            )
        )
    assert client.calls == [], "the API must not be called with invalid dates"


def test_inverted_date_range_is_rejected(harness):
    mcp, client = harness
    with pytest.raises(ToolError, match="after"):
        asyncio.run(
            mcp.call_tool(
                "get_daily_climate",
                {"location_ids": [4], "start_date": "2024-06-01", "end_date": "2024-01-01"},
            )
        )
    assert client.calls == []


@pytest.mark.parametrize("month", [0, 13])
def test_out_of_range_months_are_rejected(harness, month):
    mcp, client = harness
    with pytest.raises(ToolError, match="between 1 and 12"):
        asyncio.run(
            mcp.call_tool(
                "get_climatology",
                {"location_ids": [4], "start_month": month, "end_month": 6},
            )
        )
    assert client.calls == []


# ── error translation ─────────────────────────────────────────────────────────

def test_404_becomes_an_actionable_message(harness):
    mcp, client = harness
    client.raise_on_call = AClimateAPIError(404, "not found")
    with pytest.raises(ToolError, match="get_available"):
        asyncio.run(mcp.call_tool("get_daily_climate", {
            "location_ids": [999], "start_date": "2024-01-01", "end_date": "2024-03-31"}))


def test_server_errors_are_marked_transient(harness):
    mcp, client = harness
    client.raise_on_call = AClimateAPIError(503, "unavailable")
    with pytest.raises(ToolError, match="transient"):
        asyncio.run(mcp.call_tool("search_locations_by_name", {"name": "Palmira"}))


def test_auth_errors_never_leak_credential_details(harness):
    mcp, client = harness
    client.raise_on_call = AClimateAuthError(
        "Auth request failed (401): client_secret=super-secret-value"
    )
    with pytest.raises(ToolError) as excinfo:
        asyncio.run(mcp.call_tool("search_locations_by_name", {"name": "Palmira"}))
    assert "super-secret-value" not in str(excinfo.value)
    assert "server-side" in str(excinfo.value)


# ── output schema safety ──────────────────────────────────────────────────────
# The SDK types several date fields as datetime; pydantic serializes naive
# datetimes without a timezone, which strict RFC3339 client validators reject
# against a "date-time" format — every call fails with -32602. The MCP layer
# must therefore never advertise "date-time" in any output schema.

def test_no_tool_advertises_date_time_in_its_output_schema(harness):
    import json

    mcp, _ = harness
    offenders = [
        tool.name
        for tool in asyncio.run(mcp.list_tools())
        if "date-time" in json.dumps(tool.outputSchema or {})
    ]
    assert offenders == []


def test_date_range_tools_return_plain_iso_dates(harness):
    mcp, _ = harness
    result = call(mcp, "get_available_climate_daily_date_ranges", {"location_id": 4})
    structured = result[1] if isinstance(result, tuple) else result.structuredContent
    row = structured["result"][0]
    assert row["min_date"] == "2010-01-01"
    assert row["max_date"] == "2024-12-31"


def test_indicator_raw_returns_plain_iso_dates(harness):
    mcp, _ = harness
    result = call(mcp, "get_indicator_history", {"location_id": 4, "detail": "raw"})
    structured = result[1] if isinstance(result, tuple) else result.structuredContent
    row = structured["result"][0]
    assert row["start_date"] == "2024-01-01"
    assert row["end_date"] == "2024-01-31"


def test_indicator_summary_survives_datetime_records(harness):
    """The SDK narrative slices start_date[:10]; with the raw SDK datetimes it
    crashes ('datetime' object is not subscriptable). The MCP conversion to
    plain strings must keep the summary working."""
    mcp, _ = harness
    result = call(mcp, "get_indicator_history", {"location_id": 4})
    assert "NDD" in text_of(result)
