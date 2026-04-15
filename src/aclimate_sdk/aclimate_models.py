"""
AClimate SDK — Modelos Pydantic
Derivados directamente del spec openapi.json de api.aclimate.org
"""

from __future__ import annotations
from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── Auth ────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None


# ─── Admin Levels ─────────────────────────────────────────────────────────────

class Country(BaseModel):
    id: int
    name: str
    iso2: str

    model_config = {"json_schema_extra": {"example": {"id": 1, "name": "Colombia", "iso2": "CO"}}}


class Admin1(BaseModel):
    id: int
    name: str
    ext_id: str
    country_id: int
    country_name: str
    country_iso2: str


class Admin2(BaseModel):
    id: int
    name: str
    ext_id: str
    admin1_id: Optional[int] = None
    admin1_name: Optional[str] = None
    admin1_ext_id: Optional[str] = None
    country_id: Optional[int] = None
    country_name: Optional[str] = None
    country_iso2: Optional[str] = None


# ─── Locations ───────────────────────────────────────────────────────────────

class Location(BaseModel):
    id: int
    name: str
    ext_id: Optional[str] = None
    machine_name: Optional[str] = None
    enable: Optional[bool] = None
    altitude: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    visible: Optional[bool] = True
    admin2_id: Optional[int] = None
    admin2_name: Optional[str] = None
    admin2_ext_id: Optional[str] = None
    admin1_id: Optional[int] = None
    admin1_name: Optional[str] = None
    admin1_ext_id: Optional[str] = None
    country_id: int
    country_name: Optional[str] = None
    country_iso2: Optional[str] = None
    source: Optional[str] = None


class MeasureData(BaseModel):
    """Última medición de una variable climática en una ubicación."""
    measure_id: int
    measure_name: str
    measure_short_name: str
    measure_unit: Optional[str] = None
    value: Optional[float] = None


class LatestData(BaseModel):
    """Último dato de monitoreo registrado en una ubicación."""
    date: Optional[str] = None
    measures: list[MeasureData] = Field(default_factory=list)


class LocationWithData(BaseModel):
    """Ubicación con su último dato de monitoreo."""
    id: int
    name: str
    ext_id: Optional[str] = None
    machine_name: Optional[str] = None
    enable: Optional[bool] = None
    altitude: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    visible: Optional[bool] = True
    source_id: Optional[int] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    admin2_id: Optional[int] = None
    admin2_name: Optional[str] = None
    admin2_ext_id: Optional[str] = None
    admin1_id: Optional[int] = None
    admin1_name: Optional[str] = None
    admin1_ext_id: Optional[str] = None
    country_id: int
    country_name: Optional[str] = None
    country_iso2: Optional[str] = None
    latest_data: Optional[LatestData] = None


# ─── Climate Historical ───────────────────────────────────────────────────────

class ClimateHistoricalDaily(BaseModel):
    id: int
    location_id: int
    location_name: Optional[str] = None
    measure_id: Optional[int] = None
    measure_name: Optional[str] = None
    measure_short_name: Optional[str] = None
    measure_unit: Optional[str] = None
    date: date
    value: float


class ClimateHistoricalMonthly(BaseModel):
    id: int
    location_id: int
    location_name: Optional[str] = None
    measure_id: Optional[int] = None
    measure_name: Optional[str] = None
    measure_short_name: Optional[str] = None
    measure_unit: Optional[str] = None
    date: date
    value: float


class ClimateHistoricalClimatology(BaseModel):
    """Normal climática histórica — promedio por mes para una medida."""
    id: int
    location_id: int
    location_name: Optional[str] = None
    measure_id: Optional[int] = None
    measure_name: Optional[str] = None
    measure_short_name: Optional[str] = None
    measure_unit: Optional[str] = None
    month: int
    value: float


class MinMaxDailyRecord(BaseModel):
    measure_id: int
    measure_name: Optional[str] = None
    location_id: int
    location_name: Optional[str] = None
    min_value: float
    min_date: Optional[datetime] = None
    max_value: float
    max_date: Optional[datetime] = None


class MinMaxMonthlyRecord(BaseModel):
    measure_id: int
    measure_name: Optional[str] = None
    location_id: int
    location_name: Optional[str] = None
    min_value: float
    min_date: Optional[datetime] = None
    max_value: float
    max_date: Optional[datetime] = None


class MinMaxClimatologyRecord(BaseModel):
    measure_id: int
    measure_name: Optional[str] = None
    location_id: int
    location_name: Optional[str] = None
    min_value: float
    min_month: Optional[int] = None
    max_value: float
    max_month: Optional[int] = None


# ─── Indicators ──────────────────────────────────────────────────────────────

class IndicatorCategory(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    enable: bool
    registered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Indicator(BaseModel):
    """
    Indicador agro-climático calculado.
    Ejemplos: consecutive_rainy_days (crd), heat_stress, dry_days, frost_days
    """
    id: int
    name: str            # "consecutive_rainy_days"
    short_name: str      # "crd"
    unit: str            # "days"
    type: str            # "CLIMATE" | "AGROCLIMATIC"
    temporality: str     # "DAILY" | "MONTHLY" | "ANNUAL"
    indicator_category_id: int
    description: Optional[str] = None
    enable: bool
    registered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class IndicatorFeature(BaseModel):
    """Recomendación o característica asociada a un indicador en un país."""
    id: int
    country_indicator_id: int
    title: str
    description: Optional[str] = None
    type: str            # "recommendation" | "feature"


class IndicatorWithFeatures(Indicator):
    features: list[Any] = Field(default_factory=list)


class CountryIndicator(BaseModel):
    """Configuración de un indicador para un país específico."""
    id: int
    country_id: int
    indicator_id: int
    spatial_forecast: bool
    spatial_climate: bool
    location_forecast: bool
    location_climate: bool
    criteria: Optional[dict[str, Any]] = None


class ClimateHistoricalIndicatorRecord(BaseModel):
    """Valor histórico de un indicador agro-climático para una ubicación."""
    id: int
    indicator_id: int
    indicator_name: Optional[str] = None
    indicator_short_name: Optional[str] = None
    indicator_unit: Optional[str] = None
    location_id: int
    location_name: Optional[str] = None
    value: float
    period: Optional[str] = None       # "monthly" | "yearly"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class MinMaxIndicatorRecord(BaseModel):
    indicator_id: int
    indicator_name: Optional[str] = None
    location_id: int
    location_name: Optional[str] = None
    min_value: float
    min_date: Optional[datetime] = None
    max_value: float
    max_date: Optional[datetime] = None
