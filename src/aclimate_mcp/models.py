from pydantic import BaseModel, Field
from datetime import date, datetime

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

    Derived from the station list, merged with the /countries catalogue. The
    two disagree upstream (bug S3: the catalogue omits countries that have
    stations and lists countries that have none), so the station count is the
    ground truth for what can be queried."""

    id: int
    name: str | None = None
    iso2: str | None = None
    stations: int = Field(description="Number of stations served for this country; 0 means no location tool will return data for it")


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
    temporality: str | None = None  # "daily" | "monthly" | "annual"
