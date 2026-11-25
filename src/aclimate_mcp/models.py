from pydantic import BaseModel, Field
from datetime import date, datetime

from aclimatesdkpy.aclimate_models import CountryClimateConf, CountryIndicatorConf

# ── OUTPUT MODELS ─────────────────────────────────────────────────────────────

class AvailableDateRange(BaseModel):
    """Available data window for one measure/indicator at one location.

    min_date/max_date are the first and last dates with data. The value
    fields are what the API reports AT those dates: audits found 215 series
    where the API's own "min_value" exceeded its "max_value", so they are NOT
    the series extremes and must not be presented as such (bug S4)."""

    id: int
    name: str | None = None
    location_id: int
    location_name: str | None = None
    min_date: str | None = None  # YYYY-MM-DD, first date with data, usable as start_date
    value_at_min_date: float = Field(
        description="Value the API reports at min_date. NOT the series minimum."
    )
    max_date: str | None = None  # YYYY-MM-DD, last date with data, usable as end_date
    value_at_max_date: float = Field(
        description="Value the API reports at max_date. NOT the series maximum."
    )

class _IndicatorPoint(BaseModel):
    """Internal: SDK indicator record with dates flattened to strings, so the
    SDK narrative (which slices start_date[:10]) does not crash on datetime."""

    indicator_id: int
    indicator_name: str | None = None
    indicator_short_name: str | None = None
    indicator_unit: str | None = None
    location_id: int
    location_name: str | None = None
    value: float
    period: str | None = None
    start_date: str | None = None
    end_date: str | None = None

# ── RAW SERIES MODELS ─────────────────────────────────────────────────────────
# detail='raw' responses are grouped measure → series instead of the SDK's
# flat records, where every row repeats the same six metadata fields and a
# database row id. Measured on 90 days x 4 measures: flat ~18k tokens,
# grouped pairs ~2k (89% less). Only the row ids are dropped; every other
# field survives, hoisted to its group header. Tools take a single
# location_id, so the location is hoisted to the top level.
class ClimateMeasureSeries(BaseModel):
    """One measure's time series."""

    measure: str | None = None  # short name, e.g. "prec"
    name: str | None = None
    unit: str | None = None
    series: list[tuple[str, float]] = Field(
        default_factory=list,
        description="[date YYYY-MM-DD, value] pairs sorted by date",
    )


class ClimateSeriesResponse(BaseModel):
    """Climate time series for one location, grouped by measure."""

    location_id: int
    location_name: str | None = None
    total_points: int
    measures: list[ClimateMeasureSeries] = Field(default_factory=list)

class ClimatologyMeasureSeries(BaseModel):
    """One measure's climate normals."""

    measure: str | None = None
    name: str | None = None
    unit: str | None = None
    series: list[tuple[int, float]] = Field(
        default_factory=list,
        description="[month 1-12, value] pairs sorted by month",
    )


class ClimatologyResponse(BaseModel):
    """Climate normals for one location, grouped by measure."""

    location_id: int
    location_name: str | None = None
    total_points: int
    measures: list[ClimatologyMeasureSeries] = Field(default_factory=list)

class IndicatorSeries(BaseModel):
    """One indicator's historical series."""

    indicator_id: int
    indicator: str | None = None  # short name
    name: str | None = None
    unit: str | None = None
    period: str | None = None
    series: list[tuple[str | None, str | None, float]] = Field(
        default_factory=list,
        description="[start_date, end_date, value] triples sorted by start_date",
    )


class IndicatorHistoryResponse(BaseModel):
    """Indicator history for one location, grouped by indicator."""

    location_id: int
    location_name: str | None = None
    total_points: int
    indicators: list[IndicatorSeries] = Field(default_factory=list)


# ── CATALOGUE MODELS ──────────────────────────────────────────────────────────

class CountryStations(BaseModel):
    """One country as actually served: catalogue entry plus station count.

    Station counts are derived from the station list and remain the ground
    truth for what can be queried (bug S3: the old catalogue disagreed with
    the stations). Since the 2026-11 API update, /countries also embeds the
    climate measures and indicators configured per country; their short
    measures and indicators are surfaced here COMPLETE (full objects, not
    just names) so an agent can see what each country serves - units,
    temporalities, categories and spatial layers included - without extra
    calls."""

    id: int
    name: str | None = None
    iso2: str | None = None
    stations: int = Field(description="Number of stations served for this country; 0 means no location tool will return data for it")
    climate_measures: list[CountryClimateConf] = Field(
        default_factory=list,
        description="Climate measures configured for this country, complete: name, short_name, unit, descriptions, the spatial/location flags, and spatial_climate_conf with the GeoServer workspace/store/temporality per layer",
    )
    indicators: list[CountryIndicatorConf] = Field(
        default_factory=list,
        description="Agroclimatic indicators configured for this country, complete: type, name, short_name, unit, temporality, category, descriptions, flags, criteria and spatial workspace/store",
    )


class RasterLayer(BaseModel):
    """One GeoServer raster layer available for spatial queries.

    workspace and store are exactly the values that
    get_point_data_from_coordinates requires."""

    measure_id: int | None = None
    measure: str | None = None  # short name, e.g. "prec"
    name: str | None = None
    unit: str | None = None
    workspace: str
    store: str
    temporality: str | None = None  # "daily" | "monthly" | "annual" | "climatology"


# ── ADMINISTRATIVE AREAS ──────────────────────────────────────────────────────

class AdminAreaMatch(BaseModel):
    """One administrative area matched in a GeoServer layer, without geometry.

    The coordinates are deliberately left out: a department at full resolution
    is megabytes of vertices an agent cannot interpret. The properties carry
    the official names/codes needed to disambiguate matches, and the bbox is
    enough for spatial reasoning (which stations fall inside, a centre point
    for raster queries). detail='raw' on the tool returns the full GeoJSON."""

    properties: dict = Field(default_factory=dict, description="All attributes the layer stores for this area (official names, codes)")
    geometry_type: str | None = Field(None, description="Polygon, MultiPolygon, ...")
    vertices: int = Field(0, description="Number of coordinate points in the geometry")
    bbox: list[float] | None = Field(None, description="[west, south, east, north] in EPSG:4326")


class AdminAreaSearchResult(BaseModel):
    """Administrative areas matching a text search in one GeoServer layer."""

    layer: str
    description: str = Field(description="The search text, matched partially and case-insensitively against every text attribute of the layer")
    total_matches: int
    matches: list[AdminAreaMatch] = Field(default_factory=list)
