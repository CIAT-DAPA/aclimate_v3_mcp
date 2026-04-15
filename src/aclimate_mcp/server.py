"""
AClimate MCP Server
Expone la API v3 de AClimate al ecosistema de IA a través del protocolo MCP.

Tools disponibles:
  Geo Discovery:
    - list_countries
    - find_country_by_name
    - find_admin_region
    - find_locations
    - get_locations_with_current_data
    - get_point_data_from_coordinates

  Historical Climate:
    - get_daily_climate
    - get_monthly_climate
    - get_climatology
    - get_climate_extremes_daily
    - get_climate_extremes_climatology

  Agro-climate Indicators:
    - list_indicators_by_country
    - get_indicator_history
    - get_indicator_by_name_and_location
    - get_indicator_extremes
    - get_agro_recommendations
    - list_indicator_categories

Resources:
    - aclimate://countries
    - aclimate://indicators/{country_id}
    - aclimate://indicator-categories

Prompts:
    - analyze_climate_risk
    - compare_location_climate
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from aclimate_sdk.aclimate_models import (
    ClimateHistoricalClimatology,
    ClimateHistoricalDaily,
    ClimateHistoricalIndicatorRecord,
    ClimateHistoricalMonthly,
    Country,
    IndicatorFeature,
    Location,
    MinMaxClimatologyRecord,
    MinMaxDailyRecord,
    MinMaxIndicatorRecord,
)
from aclimate_sdk.context_builder import ContextBuilder
from aclimate_sdk.aclimate_client import AClimateClient


from aclimate_mcp.settings import Settings

# ── Setup ─────────────────────────────────────────────────────────────────────
settings = Settings()  # type: ignore[call-arg]

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("aclimate_mcp")

mcp = FastMCP(settings.server_name, log_level=settings.log_level.upper())
ctx = ContextBuilder()


# El cliente se inicializa en el lifespan del servidor

_client: AClimateClient | None = None
_client_lock = asyncio.Lock()
_client_started = False


async def get_client() -> AClimateClient:
    """
    Inicializa el cliente bajo demanda.
    Esto funciona tanto con `mcp dev` como con ejecución normal.
    """
    global _client, _client_started

    if _client is not None and _client_started:
        return _client

    async with _client_lock:
        if _client is not None and _client_started:
            return _client

        client = AClimateClient(
            base_url=settings.api_base_url,
            client_id=settings.client_id,
            client_secret=settings.client_secret,
        )

        # Abrir el cliente async, como antes hacías con `async with`
        await client.__aenter__()

        _client = client
        _client_started = True
        logger.info("AClimateClient inicializado bajo demanda")
        return _client


async def close_client() -> None:
    global _client, _client_started

    if _client is not None and _client_started:
        try:
            await _client.__aexit__(None, None, None)
            logger.info("AClimateClient cerrado correctamente")
        except Exception:
            logger.exception("Error cerrando AClimateClient")
        finally:
            _client = None
            _client_started = False


def _close_client_at_exit() -> None:
    """
    Wrapper sync para cierre al terminar el proceso.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return
        loop.run_until_complete(close_client())
    except Exception:
        pass

atexit.register(_close_client_at_exit)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _cached_get(cache_key: str, path: str, **params: Any) -> Any:
    """GET con caché automático."""
    #cached = await cache.get(cache_key)
    #if cached is not None:
    #    return cached
    #data = await get_client().get(path, **params)
    client = await get_client()
    data = await client.get(path, **params)
    #await cache.set(cache_key, data)
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS — GEO DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_countries() -> str:
    """
    Lista todos los países disponibles en la plataforma AClimate.
    Retorna nombre, ID y código ISO2 de cada país.
    Úsalo como primer paso para saber qué países tienen datos.
    """
    data = await _cached_get("countries:all", "/countries")
    countries = [Country(**c) for c in data]
    return ctx.countries_summary(countries)


@mcp.tool()
async def find_country_by_name(name: str) -> str:
    """
    Busca países en AClimate por nombre (búsqueda parcial).
    Útil para obtener el country_id cuando el usuario menciona un país.

    Args:
        name: Nombre del país a buscar (ej: "Colombia", "Ethiopia", "Angola")
    """
    cache_key = f"countries:name:{name.lower()}"
    data = await _cached_get(cache_key, "/countries/by-name", name=name)
    if not data:
        return f"No se encontró ningún país con el nombre '{name}' en AClimate."
    countries = [Country(**c) for c in data]
    return ctx.countries_summary(countries)


@mcp.tool()
async def find_admin_region(name: str, level: str = "admin1") -> str:
    """
    Busca regiones administrativas (departamentos, estados, municipios) por nombre.

    Args:
        name: Nombre de la región a buscar (ej: "Tolima", "Valle del Cauca", "Ibagué")
        level: Nivel administrativo — "admin1" (departamento/estado) o
               "admin2" (municipio/distrito)
    """
    cache_key = f"admin:{level}:name:{name.lower()}"
    if level == "admin1":
        data = await _cached_get(cache_key, "/admin1/by-name", name=name)
    else:
        data = await _cached_get(cache_key, "/admin2/by-name", name=name)

    if not data:
        return f"No se encontró ninguna región '{name}' en el nivel {level}."

    lines = [f"Regiones encontradas para '{name}' (nivel {level}):"]
    for item in data:
        lines.append(f"  • [{item.get('id')}] {item.get('name')}"
                     f" — {item.get('country_name', '')} (ext_id={item.get('ext_id', '?')})")
    return "\n".join(lines)


@mcp.tool()
async def find_locations(name: str) -> str:
    """
    Busca ubicaciones de monitoreo climático por nombre.
    Retorna ubicación, coordenadas (lat/lon), altitud y jerarquía geográfica completa.

    Úsalo SIEMPRE antes de consultar datos históricos o indicadores,
    para obtener el location_id correcto.

    Args:
        name: Nombre de la ubicación o estación (ej: "Palmira", "Ibagué", "Yopal")
    """
    cache_key = f"locations:name:{name.lower()}"
    data = await _cached_get(cache_key, "/locations/by-name", name=name)
    locations = [Location(**loc) for loc in data]
    return ctx.locations_summary(locations)


@mcp.tool()
async def get_locations_with_current_data(country_id: int, days: int = 7) -> str:
    """
    Retorna ubicaciones de un país con sus últimas mediciones de monitoreo
    (precipitación, temperatura máxima, temperatura mínima, etc.)

    Úsalo para preguntas como:
    - "¿Qué está lloviendo ahora en Colombia?"
    - "¿Qué temperatura hubo esta semana en las estaciones de Etiopía?"

    Args:
        country_id: ID del país (usa list_countries para obtenerlo)
        days: Cuántos días hacia atrás buscar datos (0 = sin límite, más reciente disponible)
    """
    cache_key = f"locations-data:country:{country_id}:days:{days}"
    data = await _cached_get(cache_key, "/locations/by-country-ids-with-data",
                             country_ids=country_id, days=days)
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
    """
    Extrae datos climáticos de capas raster de GeoServer para coordenadas GPS.
    Útil para ubicaciones sin estación de monitoreo registrada.

    Args:
        lat: Latitud (ej: 4.6097)
        lon: Longitud (ej: -74.0817)
        workspace: Workspace de GeoServer (consultar con el equipo AClimate)
        store: Store/mosaic de GeoServer (ej: "precipitation_monthly")
        start_date: Fecha inicio (YYYY-MM-DD)
        end_date: Fecha fin (YYYY-MM-DD)
        temporality: "daily", "monthly" o "annual"
    """
    data = await get_client().post("/geoserver/point-data", json_body={
        "coordinates": [[lon, lat]],
        "start_date": start_date,
        "end_date": end_date,
        "workspace": workspace,
        "store": store,
        "temporality": temporality,
    })
    return (f"Datos raster para ({lat}, {lon}) — {workspace}/{store} "
            f"[{start_date} → {end_date}]:\n{data}")


# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS — HISTORICAL CLIMATE
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_daily_climate(
    location_ids: str,
    start_date: str,
    end_date: str,
    measures: str | None = None,
) -> str:
    """
    Retorna datos climáticos históricos diarios para una o más ubicaciones.

    Args:
        location_ids: IDs de ubicaciones separados por coma (ej: "101,102")
                      Usa find_locations() para obtener los IDs.
        start_date: Fecha inicio (YYYY-MM-DD)
        end_date: Fecha fin (YYYY-MM-DD)
        measures: Medidas específicas separadas por coma (ej: "m1,tmax").
                  Si es None, retorna todas las medidas disponibles.
    """
    cache_key = f"historical-daily:{location_ids}:{start_date}:{end_date}:{measures}"

    if measures:
        data = await _cached_get(
            cache_key,
            "/historical-daily/by-date-range-and-specific-measures",
            location_ids=location_ids,
            measures=measures,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        data = await _cached_get(
            cache_key,
            "/historical-daily/by-date-range-all-measures",
            location_ids=location_ids,
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
    """
    Retorna datos climáticos históricos mensuales para una o más ubicaciones.
    Ideal para análisis de tendencias y comparaciones año a año.

    Args:
        location_ids: IDs de ubicaciones separados por coma
        start_date: Fecha inicio (YYYY-MM-DD, ej: "2020-01-01")
        end_date: Fecha fin (YYYY-MM-DD, ej: "2024-12-31")
        measures: Medidas específicas (ej: "m1" para precipitación). None = todas.
    """
    cache_key = f"historical-monthly:{location_ids}:{start_date}:{end_date}:{measures}"

    if measures:
        data = await _cached_get(
            cache_key,
            "/historical-monthly/by-date-range-and-specific-measures",
            location_ids=location_ids,
            measures=measures,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        data = await _cached_get(
            cache_key,
            "/historical-monthly/by-date-range-all-measures",
            location_ids=location_ids,
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
    """
    Retorna la climatología (normal climática histórica) de una ubicación.
    La climatología es el promedio histórico por mes — base de referencia
    para determinar si el clima actual es normal, seco o húmedo.

    Úsalo para contextualizar forecasts: "¿Qué es normal para este mes?"

    Args:
        location_ids: IDs de ubicaciones separados por coma
        start_month: Mes inicio (1-12)
        end_month: Mes fin (1-12)
        measures: Medidas específicas (None = todas)
    """
    cache_key = f"climatology:{location_ids}:{start_month}:{end_month}:{measures}"

    if measures:
        data = await _cached_get(
            cache_key,
            "/climatology/by-month-range-location-ids-and-specific-measures",
            location_ids=location_ids,
            measures=measures,
            start_month=start_month,
            end_month=end_month,
        )
    else:
        data = await _cached_get(
            cache_key,
            "/climatology/by-month-range-location-ids-all-measures",
            location_ids=location_ids,
            start_month=start_month,
            end_month=end_month,
        )

    records = [ClimateHistoricalClimatology(**r) for r in data]
    return ctx.climatology_narrative(records)


@mcp.tool()
async def get_climate_extremes_daily(location_id: int) -> str:
    """
    Retorna los extremos históricos absolutos de todas las variables climáticas
    diarias registradas en una ubicación (máximos y mínimos históricos con fechas).

    Útil para: "¿Cuánto ha llovido como máximo en un día en Palmira?"

    Args:
        location_id: ID de la ubicación (usar find_locations para obtenerlo)
    """
    cache_key = f"minmax:daily:{location_id}"
    data = await _cached_get(cache_key, "/historical-daily/minmax-by-location",
                             location_id=location_id)
    records = [MinMaxDailyRecord(**r) for r in data]
    return ctx.minmax_daily_summary(records)


@mcp.tool()
async def get_climate_extremes_climatology(location_id: int) -> str:
    """
    Retorna los extremos de la climatología mensual de una ubicación.
    Muestra en qué mes se registran históricamente los valores más altos y bajos.

    Args:
        location_id: ID de la ubicación
    """
    cache_key = f"minmax:climatology:{location_id}"
    data = await _cached_get(cache_key, "/climatology/minmax-by-location",
                             location_id=location_id)
    records = [MinMaxClimatologyRecord(**r) for r in data]
    return ctx.minmax_climatology_summary(records)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS — AGRO-CLIMATE INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_indicators_by_country(
    country_id: int,
    indicator_type: str = "CLIMATE",
    temporality: str | None = None,
) -> str:
    """
    Lista los indicadores agro-climáticos disponibles para un país.
    Incluye nombre, unidad, temporalidad y tipo de cada indicador.

    Args:
        country_id: ID del país
        indicator_type: "CLIMATE" o "AGROCLIMATIC"
        temporality: "DAILY", "MONTHLY" o "ANNUAL" (None = todos)
    """
    cache_key = f"indicators:country:{country_id}:{indicator_type}:{temporality}"
    data = await _cached_get(
        cache_key,
        "/indicator-mng/by-country",
        country_id=country_id,
        type=indicator_type,
        temporality=temporality,
    )
    return ctx.indicators_catalog_summary(data)


@mcp.tool()
async def get_indicator_history(location_id: int) -> str:
    """
    Obtiene todos los registros históricos de indicadores agro-climáticos
    para una ubicación específica.

    Incluye indicadores como: días consecutivos de lluvia (crd),
    estrés por calor, días secos, días de helada, etc.

    Args:
        location_id: ID de la ubicación (usar find_locations para obtenerlo)
    """
    cache_key = f"indicators:history:location:{location_id}"
    data = await _cached_get(cache_key, "/indicator/by-location-id",
                             location_id=location_id)
    records = [ClimateHistoricalIndicatorRecord(**r) for r in data]
    return ctx.indicator_narrative(records)


@mcp.tool()
async def get_indicator_by_name_and_location(
    location_name: str,
    indicator_name: str,
) -> str:
    """
    Obtiene el historial de un indicador agro-climático específico
    para una ubicación buscada por nombre.

    Indicadores comunes:
      - "consecutive_rainy_days" (crd) — días consecutivos de lluvia
      - "heat_stress" — estrés por calor
      - "dry_days" — días secos consecutivos
      - "frost_days" — días de helada
    Usa list_indicators_by_country para ver todos los disponibles.

    Args:
        location_name: Nombre de la ubicación (ej: "Palmira", "Ibagué")
        indicator_name: Nombre del indicador (ej: "consecutive_rainy_days")
    """
    cache_key = f"indicators:name:{indicator_name}:loc:{location_name.lower()}"
    data = await _cached_get(
        cache_key,
        "/indicator/by-location-and-indicator-name",
        location_name=location_name,
        indicator_name=indicator_name,
    )
    records = [ClimateHistoricalIndicatorRecord(**r) for r in data]
    return ctx.indicator_narrative(records, indicator_name)


@mcp.tool()
async def get_indicator_by_period(
    location_id: int,
    indicator_id: int,
    start_date: str,
    end_date: str,
    period: str = "monthly",
) -> str:
    """
    Obtiene el historial de un indicador agro-climático filtrado por
    período y rango de fechas.

    Args:
        location_id: ID de la ubicación
        indicator_id: ID del indicador (usar list_indicators_by_country)
        start_date: Fecha inicio (YYYY-MM-DD)
        end_date: Fecha fin (YYYY-MM-DD)
        period: "monthly" o "yearly"
    """
    cache_key = f"indicators:period:{location_id}:{indicator_id}:{start_date}:{end_date}:{period}"
    data = await _cached_get(
        cache_key,
        "/indicator/by-location-date-period",
        location_id=location_id,
        indicator_id=indicator_id,
        start_date=start_date,
        end_date=end_date,
        period=period,
    )
    records = [ClimateHistoricalIndicatorRecord(**r) for r in data]
    return ctx.indicator_narrative(records)


@mcp.tool()
async def get_indicator_extremes(location_id: int) -> str:
    """
    Retorna los valores extremos históricos de todos los indicadores
    agro-climáticos para una ubicación.

    Útil para: "¿Cuál fue el peor estrés por calor registrado en Ibagué?"

    Args:
        location_id: ID de la ubicación
    """
    cache_key = f"minmax:indicators:{location_id}"
    data = await _cached_get(cache_key, "/indicator/minmax-by-location",
                             location_id=location_id)
    records = [MinMaxIndicatorRecord(**r) for r in data]
    return ctx.indicator_extremes_narrative(records)


@mcp.tool()
async def get_agro_recommendations(
    indicator_id: int,
    country_id: int,
    feature_type: str = "recommendation",
) -> str:
    """
    Obtiene recomendaciones agronómicas o características para un indicador
    en un país específico. Las recomendaciones provienen de expertos de CIAT.

    Args:
        indicator_id: ID del indicador (usar list_indicators_by_country)
        country_id: ID del país
        feature_type: "recommendation" (recomendaciones de manejo) o
                      "feature" (características del indicador)
    """
    cache_key = f"indicators:features:{indicator_id}:{country_id}:{feature_type}"
    data = await _cached_get(
        cache_key,
        "/indicator-features/by-indicator-and-country",
        indicator_id=indicator_id,
        country_id=country_id,
        type=feature_type,
    )
    features = [IndicatorFeature(**f) for f in data]
    return ctx.recommendations_narrative(features)


@mcp.tool()
async def list_indicator_categories(country_id: int | None = None) -> str:
    """
    Lista las categorías de indicadores disponibles.
    Ejemplos: "Extreme Temperature", "Heat Stress", "Precipitation", etc.

    Args:
        country_id: Si se especifica, solo categorías disponibles en ese país
    """
    if country_id:
        cache_key = f"indicators:categories:country:{country_id}"
        data = await _cached_get(
            cache_key,
            "/indicator-category-mng/by-country",
            country_id=country_id,
        )
    else:
        cache_key = "indicators:categories:all"
        data = await _cached_get(cache_key, "/indicator-category-mng/all")

    if not data:
        return "No se encontraron categorías de indicadores."
    lines = ["Categorías de indicadores agro-climáticos:"]
    for cat in data:
        desc = cat.get("description", "")
        lines.append(f"  • [{cat.get('id')}] {cat.get('name')}"
                     + (f" — {desc}" if desc else ""))
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# RESOURCES — Lecturas directas sin tool call
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.resource("aclimate://countries")
async def resource_countries() -> str:
    """List all countries in AClimate."""
    data = await _cached_get("countries:all", "/countries")
    #print(data)
    countries = [Country(**c) for c in data]
    return ctx.countries_summary(countries)


@mcp.resource("aclimate://indicators/{country_id}")
async def resource_indicators(country_id: int) -> str:
    """Catálogo de indicadores agro-climáticos disponibles para un país."""
    cache_key = f"indicators:country:{country_id}:CLIMATE:None"
    data = await _cached_get(cache_key, "/indicator-mng/by-country",
                             country_id=country_id)
    return ctx.indicators_catalog_summary(data)


@mcp.resource("aclimate://indicator-categories")
async def resource_indicator_categories() -> str:
    """Categorías de indicadores agro-climáticos."""
    data = await _cached_get("indicators:categories:all",
                             "/indicator-category-mng/all")
    lines = ["Categorías de indicadores:"]
    for cat in data:
        lines.append(f"  • [{cat.get('id')}] {cat.get('name')}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPTS — Plantillas de razonamiento agronómico
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.prompt()
def analyze_climate_risk(location_name: str, crop: str, season: str) -> str:
    """
    Plantilla para análisis completo de riesgo climático para un cultivo.
    Guía al LLM a usar las tools en el orden correcto.
    """
    return f"""Realiza un análisis de riesgo climático para el cultivo de {crop}
en {location_name} durante {season}.

Sigue estos pasos en orden:

1. Usa find_locations(name="{location_name}") para obtener el location_id y coordenadas.
2. Usa list_countries() si necesitas identificar el country_id.
3. Usa get_climatology(location_ids=<id>, start_month=<inicio>, end_month=<fin>)
   para obtener las normales climáticas del período de interés.
4. Usa get_indicator_by_name_and_location(
       location_name="{location_name}",
       indicator_name="consecutive_rainy_days")
   para evaluar el riesgo hídrico.
5. Usa get_indicator_by_name_and_location(
       location_name="{location_name}",
       indicator_name="heat_stress")
   para evaluar el riesgo térmico (si disponible).
6. Usa get_indicator_extremes(location_id=<id>) para conocer los peores escenarios históricos.
7. Usa get_agro_recommendations(indicator_id=<id>, country_id=<id>)
   para obtener recomendaciones de expertos de CIAT.

Finalmente, sintetiza:
- Nivel de riesgo hídrico (exceso o déficit de lluvia)
- Nivel de riesgo térmico
- Comparación con la climatología normal
- Recomendaciones concretas para {crop} en {season}
"""


@mcp.prompt()
def compare_location_climate(location_a: str, location_b: str, variable: str) -> str:
    """Compara el clima de dos ubicaciones para una variable específica."""
    return f"""Compara el comportamiento climático de {variable} entre
{location_a} y {location_b}.

Pasos:
1. Usa find_locations(name="{location_a}") y find_locations(name="{location_b}")
   para obtener los IDs de cada ubicación.
2. Usa get_climatology(...) para ambas ubicaciones (todos los meses).
3. Usa get_climate_extremes_climatology(...) para ambas.
4. Compara: ¿cuál tiene mayor {variable}? ¿En qué meses difieren más?
5. Explica las implicaciones agrícolas de estas diferencias.
"""


@mcp.prompt()
def summarize_current_conditions(country_name: str) -> str:
    """Resume las condiciones climáticas actuales de un país."""
    return f"""Resume las condiciones climáticas actuales en {country_name}.

Pasos:
1. Usa find_country_by_name(name="{country_name}") para obtener el country_id.
2. Usa get_locations_with_current_data(country_id=<id>, days=7)
   para obtener las últimas mediciones de todas las estaciones.
3. Identifica patrones: ¿qué regiones tienen más lluvia? ¿Dónde hace más calor?
4. Menciona cualquier condición extrema o inusual.
5. Relaciona con la temporada actual del año.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# LIFESPAN — Init y cleanup del cliente
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Entry point del MCP Server."""
    import asyncio

    async def run() -> None:
        logger.info(
            "AClimate MCP Server iniciado — API: %s",
            settings.api_base_url,
        )
        await mcp.run_sse_async()

    asyncio.run(run())

    """
    async def run() -> None:
        
        global _client
        async with AClimateClient(
            base_url=settings.api_base_url,
            client_id=settings.client_id,
            client_secret=settings.client_secret,
        ) as client:
            _client = client
            logger.info(
                "AClimate MCP Server iniciado — API: %s", settings.api_base_url
            )
            #await mcp.run_async()
            await mcp.run_sse_async()
    asyncio.run(run())
    """


if __name__ == "__main__":
    #mcp.run(transport="stdio")
    main()
