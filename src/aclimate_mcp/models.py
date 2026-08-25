from pydantic import BaseModel, Field
from datetime import date, datetime

# ── OUTPUT MODELS ─────────────────────────────────────────────────────────────

class AvailableDateRange(BaseModel):
    """Available data window for one measure/indicator at one location."""

    id: int
    name: str | None = None
    location_id: int
    location_name: str | None = None
    min_value: float
    min_date: str | None = None  # YYYY-MM-DD, usable as start_date
    max_value: float
    max_date: str | None = None  # YYYY-MM-DD, usable as end_date

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
