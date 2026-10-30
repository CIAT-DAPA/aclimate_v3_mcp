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


def make_daily_records(count, location_id=4, measure=("prec", "Precipitation", "mm")):
    short, name, unit = measure
    return [
        ClimateHistoricalDateRecord(
            id=i,
            location_id=location_id,
            location_name="Palmira",
            measure_id=1,
            measure_name=name,
            measure_short_name=short,
            measure_unit=unit,
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
        self.indicator_response = None
        self.locations_response = []
        self.raw_get_response = [
            {
                "id": 11, "country_id": 6, "measure_id": 1,
                "spatial_forecast": False, "spatial_climate": True,
                "location_forecast": False, "location_climate": True,
                "spatial_climate_conf": [
                    {"temporality": "daily", "workspace": "climate", "store": "chirps_daily"},
                    {"temporality": "monthly", "workspace": "climate", "store": "chirps_monthly"},
                ],
            }
        ]
        self.raise_on_call = None

    def _record(self, entry):
        if self.raise_on_call is not None:
            raise self.raise_on_call
        self.calls.append(entry)

    async def get_locations_by_search(self, q):
        self._record(("search", q))
        return self.locations_response

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

    @staticmethod
    def make_indicator_records(location_id, spec):
        """spec: list of (indicator_id, name, unit, [(start, end, value), ...])"""
        from aclimatesdkpy.aclimate_models import ClimateHistoricalIndicatorRecord

        records, next_id = [], 1
        for indicator_id, name, unit, points in spec:
            for start, end, value in points:
                records.append(
                    ClimateHistoricalIndicatorRecord(
                        id=next_id, indicator_id=indicator_id, indicator_name=name,
                        indicator_unit=unit, location_id=location_id,
                        location_name="Palmira", value=value, period="monthly",
                        start_date=start, end_date=end,
                    )
                )
                next_id += 1
        return records

    async def get_indicator_by_location_id(self, location_id):
        self._record(("indicator_history", location_id))
        if self.indicator_response is not None:
            return self.indicator_response
        return self.make_indicator_records(location_id, [
            (9, "NDD", "days", [
                (datetime.datetime(2024, 1, 1), datetime.datetime(2024, 1, 31), 3.5),
                (datetime.datetime(2024, 2, 1), datetime.datetime(2024, 2, 28), 5.0),
            ]),
            (24, "Inicio de la canicula", "julian day", [
                (datetime.datetime(2024, 1, 1), datetime.datetime(2024, 12, 31), 190.0),
            ]),
        ])

    async def get_countries(self):
        self._record(("countries",))
        from aclimatesdkpy.aclimate_models import Country

        return [
            Country(id=2, name="HONDURAS", iso2="HN"),
            Country(id=6, name="GUATEMALA", iso2="GT"),
        ]

    async def get_climate_measures_by_country(self, country_id):
        self._record(("climate_measures", country_id))
        from aclimatesdkpy.aclimate_models import ClimateMeasure

        return [ClimateMeasure(id=1, name="Precipitation", short_name="prec", unit="mm", enable=True)]

    async def get(self, path, **params):
        self._record(("raw_get", path, params))
        return self.raw_get_response

    async def get_indicator_features_by_indicator_and_country(self, indicator_id, country_id, type):
        self._record(("features", indicator_id, country_id, type))
        return []

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


def structured_of(result):
    payload = result[1] if isinstance(result, tuple) else result.structuredContent
    return payload["result"] if "result" in payload else payload


# ── registration and naming ───────────────────────────────────────────────────

def test_expected_tools_register(harness):
    mcp, _ = harness
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert "get_daily_climate" in names
    assert "search_locations_by_name" in names
    assert "get_available_climate_daily_date_ranges" in names, (
        "the misspelled 'daliy' tool name must stay fixed"
    )
    assert "get_available_climate_daliy_date_ranges" not in names


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


def test_location_id_schema_is_strict(harness):
    """A list where a single int is expected must be rejected, not coerced."""
    mcp, _ = harness
    with pytest.raises(Exception):
        call(
            mcp,
            "get_daily_climate",
            {"location_id": [4], "start_date": "2024-01-01", "end_date": "2024-03-31"},
        )


# ── detail: summary vs raw ────────────────────────────────────────────────────

def test_summary_is_the_default_and_returns_a_narrative(harness):
    mcp, client = harness
    result = call(
        mcp,
        "get_daily_climate",
        {"location_id": 4, "start_date": "2024-01-01", "end_date": "2024-03-31"},
    )
    text = text_of(result)
    assert "Palmira" in text
    assert len(text) < 2000, "the summary must be compact, not the raw records"
    assert client.calls[-1] == ("daily", [4], "2024-01-01", "2024-03-31")


def test_raw_returns_grouped_series_when_under_the_cap(harness):
    """raw is grouped measure → [date, value] pairs with the location hoisted,
    not the SDK's flat records where every row repeats the metadata."""
    mcp, client = harness
    client.daily_response = make_daily_records(10)
    result = call(
        mcp,
        "get_daily_climate",
        {"location_id": 4, "start_date": "2024-01-01", "end_date": "2024-03-31", "detail": "raw"},
    )
    payload = structured_of(result)
    assert payload["location_id"] == 4
    assert payload["location_name"] == "Palmira"
    assert payload["total_points"] == 10
    measure = payload["measures"][0]
    assert measure["measure"] == "prec"
    assert measure["unit"] == "mm"
    assert measure["series"][0] == ["2024-01-01", 0.0]
    dates = [point[0] for point in measure["series"]]
    assert dates == sorted(dates)
    assert "id" not in measure, "database row ids must not travel to the agent"


def test_raw_groups_multiple_measures(harness):
    mcp, client = harness
    client.daily_response = make_daily_records(6) + make_daily_records(
        3, measure=("tmax", "Maximum temperature", "C")
    )
    result = call(
        mcp,
        "get_daily_climate",
        {"location_id": 4, "start_date": "2024-01-01", "end_date": "2024-03-31", "detail": "raw"},
    )
    payload = structured_of(result)
    assert payload["total_points"] == 9
    assert {m["measure"] for m in payload["measures"]} == {"prec", "tmax"}


def test_raw_with_no_data_returns_an_empty_grouping(harness):
    mcp, client = harness
    client.daily_response = []
    result = call(
        mcp,
        "get_daily_climate",
        {"location_id": 4, "start_date": "2024-01-01", "end_date": "2024-03-31", "detail": "raw"},
    )
    payload = structured_of(result)
    assert payload["location_id"] == 4
    assert payload["total_points"] == 0
    assert payload["measures"] == []


def test_raw_above_the_cap_is_rejected_with_guidance(harness):
    mcp, client = harness
    client.daily_response = make_daily_records(RAW_RECORD_LIMIT + 1)
    with pytest.raises(ToolError, match="summary"):
        asyncio.run(
            mcp.call_tool(
                "get_daily_climate",
                {"location_id": 4, "start_date": "2024-01-01", "end_date": "2024-12-31", "detail": "raw"},
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
                {"location_id": 4, "start_date": bad, "end_date": "2024-03-31"},
            )
        )
    assert client.calls == [], "the API must not be called with invalid dates"


def test_inverted_date_range_is_rejected(harness):
    mcp, client = harness
    with pytest.raises(ToolError, match="after"):
        asyncio.run(
            mcp.call_tool(
                "get_daily_climate",
                {"location_id": 4, "start_date": "2024-06-01", "end_date": "2024-01-01"},
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
                {"location_id": 4, "start_month": month, "end_month": 6},
            )
        )
    assert client.calls == []


# ── error translation ─────────────────────────────────────────────────────────

def test_404_becomes_an_actionable_message(harness):
    mcp, client = harness
    client.raise_on_call = AClimateAPIError(404, "not found")
    with pytest.raises(ToolError, match="get_available"):
        asyncio.run(mcp.call_tool("get_daily_climate", {
            "location_id": 999, "start_date": "2024-01-01", "end_date": "2024-03-31"}))


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
    row = structured_of(result)[0]
    assert row["min_date"] == "2010-01-01"
    assert row["max_date"] == "2024-12-31"
    # Bug S4: the API's min/max values are not series extremes; the renamed
    # fields must carry no such claim.
    assert "min_value" not in row and "max_value" not in row
    assert row["value_at_min_date"] == 0.0
    assert row["value_at_max_date"] == 40.0


def test_indicator_raw_is_grouped_with_plain_iso_dates(harness):
    mcp, _ = harness
    result = call(mcp, "get_indicator_history", {"location_id": 4, "detail": "raw"})
    payload = structured_of(result)
    assert payload["location_id"] == 4
    assert payload["total_points"] == 3
    by_id = {i["indicator_id"]: i for i in payload["indicators"]}
    assert set(by_id) == {9, 24}
    assert by_id[9]["name"] == "NDD"
    assert by_id[9]["unit"] == "days"
    assert by_id[9]["series"][0] == ["2024-01-01", "2024-01-31", 3.5]


def test_indicator_summary_survives_datetime_records(harness):
    """The SDK narrative slices start_date[:10]; with the raw SDK datetimes it
    crashes ('datetime' object is not subscriptable). The MCP conversion to
    plain strings must keep the summary working."""
    mcp, _ = harness
    result = call(mcp, "get_indicator_history", {"location_id": 4})
    assert "NDD" in text_of(result)


# ── bug-report fixes (S1, S2, S3, S5, S10) ────────────────────────────────────

def test_indicator_summary_is_per_indicator_not_pooled(harness):
    """Bug S1: one narrative per indicator, each with its own name, unit and
    record count, instead of pooling every indicator into one statistic."""
    mcp, _ = harness
    text = text_of(call(mcp, "get_indicator_history", {"location_id": 4}))
    assert "NDD" in text and "Inicio de la canicula" in text
    # two narratives, each counting only its own records
    assert text.count("Registros: ") == 2
    assert "Registros: 2 (monthly)" in text
    assert "Registros: 1 (monthly)" in text
    assert "Registros: 3" not in text, "records must not be pooled across indicators"


def test_indicator_filters_by_indicator_id(harness):
    mcp, _ = harness
    result = call(mcp, "get_indicator_history", {"location_id": 4, "indicator_id": 24, "detail": "raw"})
    payload = structured_of(result)
    assert payload["total_points"] == 1
    assert [i["indicator_id"] for i in payload["indicators"]] == [24]
    text = text_of(call(mcp, "get_indicator_history", {"location_id": 4, "indicator_id": 24}))
    assert "Inicio de la canicula" in text and "NDD" not in text


def test_indicator_filters_by_dates(harness):
    mcp, _ = harness
    result = call(
        mcp, "get_indicator_history",
        {"location_id": 4, "start_date": "2024-02-01", "end_date": "2024-02-28", "detail": "raw"},
    )
    payload = structured_of(result)
    assert payload["total_points"] == 1
    assert payload["indicators"][0]["series"] == [["2024-02-01", "2024-02-28", 5.0]]


def test_indicator_invalid_filter_date_is_rejected(harness):
    mcp, client = harness
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        asyncio.run(mcp.call_tool("get_indicator_history", {"location_id": 4, "start_date": "febrero"}))
    assert client.calls == []


def test_indicator_raw_cap_applies_after_filtering(harness):
    """Bug S2: a station with more records than the raw limit must still be
    readable through the filters."""
    import datetime as dt

    mcp, client = harness
    big = [(dt.datetime(2000, 1, 1) + dt.timedelta(days=i), dt.datetime(2000, 1, 2) + dt.timedelta(days=i), float(i)) for i in range(RAW_RECORD_LIMIT + 1)]
    client.indicator_response = client.make_indicator_records(172, [
        (19, "Epoca lluviosa", "julian day", big),
        (24, "Inicio de la canicula", "julian day", [(dt.datetime(2024, 1, 1), dt.datetime(2024, 12, 31), 190.0)]),
    ])
    with pytest.raises(ToolError, match="indicator_id"):
        asyncio.run(mcp.call_tool("get_indicator_history", {"location_id": 172, "detail": "raw"}))
    result = call(mcp, "get_indicator_history", {"location_id": 172, "indicator_id": 24, "detail": "raw"})
    assert structured_of(result)["total_points"] == 1


def test_indicator_empty_after_filters_returns_guidance(harness):
    mcp, _ = harness
    text = text_of(call(mcp, "get_indicator_history", {"location_id": 4, "indicator_id": 999}))
    assert "No indicator data" in text and "filters" in text


def test_features_empty_result_is_explicit(harness):
    """Bug S10: an empty catalogue must say so instead of returning an empty body."""
    mcp, _ = harness
    text = text_of(call(mcp, "get_features_indicator", {"indicator_id": 7, "country_id": 5}))
    assert "No" in text and "not an error" in text


def test_list_raster_layers_exposes_workspace_and_store(harness):
    """Bug S5: get_point_data_from_coordinates was unusable because nothing
    listed valid workspace/store values."""
    mcp, client = harness
    result = call(mcp, "list_raster_layers", {"country_id": 6})
    layers = structured_of(result)
    assert {(l["workspace"], l["store"], l["temporality"]) for l in layers} == {
        ("climate", "chirps_daily", "daily"),
        ("climate", "chirps_monthly", "monthly"),
    }
    assert layers[0]["measure"] == "prec"
    assert ("raw_get", "/countries/6/climate-measures/configuration", {}) in client.calls


def test_list_raster_layers_empty_is_explicit(harness):
    mcp, client = harness
    client.raw_get_response = []
    text = text_of(call(mcp, "list_raster_layers", {"country_id": 3}))
    assert "No raster layers" in text


def test_countries_resource_is_derived_from_stations(harness):
    """Bug S3: the countries resource must include every country that has
    stations (El Salvador was missing) and expose station counts so countries
    without stations are recognisable."""
    import json

    from aclimatesdkpy.aclimate_models import Location

    mcp, client = harness
    from aclimate_mcp.resources import register_resources

    async def get_client():
        return client

    register_resources(mcp=mcp, get_client=get_client)
    client.locations_response = [
        Location(id=100 + i, name=f"S{i}", country_id=5, country_name="EL SALVADOR", country_iso2="SV")
        for i in range(3)
    ] + [
        Location(id=200, name="G1", country_id=6, country_name="GUATEMALA", country_iso2="GT")
    ]
    contents = asyncio.run(mcp.read_resource("aclimate://countries"))
    payload = json.loads(list(contents)[0].content)
    by_id = {c["id"]: c for c in payload}
    assert by_id[5]["stations"] == 3 and by_id[5]["name"] == "EL SALVADOR"
    assert by_id[6]["stations"] == 1
    assert by_id[2]["stations"] == 0, "catalogue-only countries must show 0 stations"
    assert payload[0]["id"] == 5, "countries with stations come first"
