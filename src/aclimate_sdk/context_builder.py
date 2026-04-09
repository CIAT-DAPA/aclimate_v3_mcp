"""
AClimate SDK — ContextBuilder
Transforma datos crudos de la API en narrativa legible para LLMs.

El principio: el LLM no debe recibir JSON crudo con IDs opacos.
Debe recibir texto que pueda razonar directamente, con contexto agronómico.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from aclimate_models import (
    ClimateHistoricalClimatology,
    ClimateHistoricalDaily,
    ClimateHistoricalIndicatorRecord,
    ClimateHistoricalMonthly,
    Country,
    IndicatorFeature,
    Location,
    LocationWithData,
    MinMaxClimatologyRecord,
    MinMaxDailyRecord,
    MinMaxIndicatorRecord,
)

MONTH_NAMES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


class ContextBuilder:
    """Convierte respuestas de la API AClimate v3 en texto para LLMs."""

    # ── Geo ──────────────────────────────────────────────────────────────────

    def countries_summary(self, countries: list[Country]) -> str:
        if not countries:
            return "No se encontraron países en AClimate."
        lines = ["Países disponibles en AClimate:"]
        for c in countries:
            lines.append(f"  • {c.name} (id={c.id}, iso2={c.iso2})")
        return "\n".join(lines)

    def locations_summary(self, locations: list[Location]) -> str:
        if not locations:
            return "No se encontraron ubicaciones con ese nombre."

        lines = [f"Se encontraron {len(locations)} ubicación(es):"]
        for loc in locations:
            parts = [f"  • [{loc.id}] {loc.name}"]
            if loc.admin2_name:
                parts.append(f"    Municipio: {loc.admin2_name}")
            if loc.admin1_name:
                parts.append(f"    Región: {loc.admin1_name}")
            if loc.country_name:
                parts.append(f"    País: {loc.country_name}")
            if loc.latitude and loc.longitude:
                parts.append(f"    Coordenadas: {loc.latitude:.4f}, {loc.longitude:.4f}")
            if loc.altitude:
                parts.append(f"    Altitud: {loc.altitude:.0f} msnm")
            lines.extend(parts)
        return "\n".join(lines)

    def current_conditions_summary(self, locations_data: list[dict[str, Any]]) -> str:
        if not locations_data:
            return "No se encontraron datos de monitoreo recientes."

        # Parseamos manualmente porque la respuesta puede ser dicts crudos
        lines = [f"Condiciones actuales ({len(locations_data)} ubicaciones):"]
        for item in locations_data:
            name = item.get("name", "?")
            admin1 = item.get("admin1_name", "")
            country = item.get("country_name", "")
            loc_id = item.get("id", "?")
            header = f"\n  📍 {name}"
            if admin1:
                header += f", {admin1}"
            if country:
                header += f" ({country}) — id={loc_id}"
            lines.append(header)

            latest = item.get("latest_data")
            if not latest:
                lines.append("    Sin datos recientes")
                continue

            d = latest.get("date", "fecha desconocida")
            lines.append(f"    Última medición: {d}")

            for m in latest.get("measures", []):
                val = m.get("value")
                unit = m.get("measure_unit", "")
                mname = m.get("measure_name", m.get("measure_short_name", "?"))
                if val is not None:
                    lines.append(f"    • {mname}: {val:.1f} {unit}")
                else:
                    lines.append(f"    • {mname}: sin dato")

        return "\n".join(lines)

    # ── Historical Climate ────────────────────────────────────────────────────

    def daily_climate_summary(self, records: list[ClimateHistoricalDaily]) -> str:
        if not records:
            return "No se encontraron datos históricos diarios para el período."

        # Agrupamos por medida
        by_measure: dict[str, list[ClimateHistoricalDaily]] = defaultdict(list)
        for r in records:
            key = f"{r.measure_name or r.measure_short_name} ({r.measure_unit or ''})"
            by_measure[key].append(r)

        loc_name = records[0].location_name or f"ubicación {records[0].location_id}"
        lines = [f"Datos históricos diarios — {loc_name}:"]

        for measure, recs in by_measure.items():
            recs_sorted = sorted(recs, key=lambda x: x.date)
            values = [r.value for r in recs_sorted]
            avg = sum(values) / len(values)
            min_r = min(recs_sorted, key=lambda x: x.value)
            max_r = max(recs_sorted, key=lambda x: x.value)
            lines.append(f"\n  {measure.strip()}:")
            lines.append(f"    Período: {recs_sorted[0].date} → {recs_sorted[-1].date} ({len(recs)} días)")
            lines.append(f"    Promedio: {avg:.2f}")
            lines.append(f"    Mínimo: {min_r.value:.2f} el {min_r.date}")
            lines.append(f"    Máximo: {max_r.value:.2f} el {max_r.date}")

        return "\n".join(lines)

    def monthly_climate_summary(self, records: list[ClimateHistoricalMonthly]) -> str:
        if not records:
            return "No se encontraron datos históricos mensuales."

        by_measure: dict[str, list[ClimateHistoricalMonthly]] = defaultdict(list)
        for r in records:
            key = f"{r.measure_name or r.measure_short_name} ({r.measure_unit or ''})"
            by_measure[key].append(r)

        loc_name = records[0].location_name or f"ubicación {records[0].location_id}"
        lines = [f"Datos históricos mensuales — {loc_name}:"]

        for measure, recs in by_measure.items():
            recs_sorted = sorted(recs, key=lambda x: x.date)
            values = [r.value for r in recs_sorted]
            avg = sum(values) / len(values)
            min_r = min(recs_sorted, key=lambda x: x.value)
            max_r = max(recs_sorted, key=lambda x: x.value)
            lines.append(f"\n  {measure.strip()}:")
            lines.append(f"    Período: {recs_sorted[0].date} → {recs_sorted[-1].date}")
            lines.append(f"    Promedio mensual: {avg:.2f}")
            lines.append(f"    Mes más bajo: {min_r.value:.2f} ({min_r.date})")
            lines.append(f"    Mes más alto: {max_r.value:.2f} ({max_r.date})")

        return "\n".join(lines)

    def climatology_narrative(self, records: list[ClimateHistoricalClimatology]) -> str:
        """
        Construye una narrativa de la normal climática histórica por mes.
        Ejemplo: "En Palmira, la precipitación normal de marzo es 89.4 mm,
        con pico en mayo (167 mm) y mínimo en agosto (12 mm)."
        """
        if not records:
            return "No se encontraron datos de climatología para esta ubicación."

        by_measure: dict[str, list[ClimateHistoricalClimatology]] = defaultdict(list)
        for r in records:
            key = r.measure_name or r.measure_short_name or "variable"
            by_measure[key].append(r)

        loc_name = records[0].location_name or f"ubicación {records[0].location_id}"
        lines = [f"Climatología histórica (normales climáticas) — {loc_name}:"]

        for measure, recs in by_measure.items():
            recs_sorted = sorted(recs, key=lambda x: x.month)
            unit = recs[0].measure_unit or ""
            peak = max(recs_sorted, key=lambda x: x.value)
            trough = min(recs_sorted, key=lambda x: x.value)

            lines.append(f"\n  {measure} [{unit}]:")
            for r in recs_sorted:
                bar = "█" * int(r.value / (peak.value or 1) * 20)
                lines.append(f"    {MONTH_NAMES.get(r.month, r.month):>10}: {r.value:>8.1f}  {bar}")
            lines.append(f"    → Pico: {MONTH_NAMES.get(peak.month, peak.month)} ({peak.value:.1f} {unit})")
            lines.append(f"    → Mínimo: {MONTH_NAMES.get(trough.month, trough.month)} ({trough.value:.1f} {unit})")

        return "\n".join(lines)

    def minmax_daily_summary(self, records: list[MinMaxDailyRecord]) -> str:
        if not records:
            return "No se encontraron extremos históricos."
        loc_name = records[0].location_name or f"ubicación {records[0].location_id}"
        lines = [f"Extremos históricos (diarios) — {loc_name}:"]
        for r in records:
            name = r.measure_name or str(r.measure_id)
            lines.append(f"  • {name}: mín={r.min_value:.2f} ({r.min_date or '?'})"
                         f"  |  máx={r.max_value:.2f} ({r.max_date or '?'})")
        return "\n".join(lines)

    def minmax_climatology_summary(self, records: list[MinMaxClimatologyRecord]) -> str:
        if not records:
            return "No se encontraron extremos de climatología."
        loc_name = records[0].location_name or f"ubicación {records[0].location_id}"
        lines = [f"Extremos climatológicos — {loc_name}:"]
        for r in records:
            name = r.measure_name or str(r.measure_id)
            min_m = MONTH_NAMES.get(r.min_month or 0, str(r.min_month))
            max_m = MONTH_NAMES.get(r.max_month or 0, str(r.max_month))
            lines.append(f"  • {name}: mín={r.min_value:.2f} en {min_m}"
                         f"  |  máx={r.max_value:.2f} en {max_m}")
        return "\n".join(lines)

    # ── Indicators ───────────────────────────────────────────────────────────

    def indicator_narrative(
        self,
        records: list[ClimateHistoricalIndicatorRecord],
        indicator_name: str | None = None,
    ) -> str:
        """
        Construye narrativa para un indicador agro-climático.

        En lugar de datos crudos, el LLM recibe:
        "En Palmira, los días consecutivos de lluvia (CRD) promediaron 8.2
        días/mes en 2024. El período más crítico fue enero (14 días). En agosto
        se registró el mínimo (1 día)."
        """
        if not records:
            name = indicator_name or "el indicador"
            return f"No se encontraron registros históricos para {name}."

        loc_name = records[0].location_name or f"ubicación {records[0].location_id}"
        ind_name = records[0].indicator_name or indicator_name or "indicador"
        unit = records[0].indicator_unit or ""
        period = records[0].period or "período"

        values = [r.value for r in records]
        avg = sum(values) / len(values)
        max_r = max(records, key=lambda x: x.value)
        min_r = min(records, key=lambda x: x.value)

        lines = [
            f"Indicador agro-climático: {ind_name} [{unit}]",
            f"Ubicación: {loc_name}",
            f"Registros: {len(records)} ({period})",
            f"",
            f"Resumen estadístico:",
            f"  Promedio: {avg:.2f} {unit}",
            f"  Valor máximo: {max_r.value:.2f} {unit}"
            + (f" (período: {max_r.start_date})" if max_r.start_date else ""),
            f"  Valor mínimo: {min_r.value:.2f} {unit}"
            + (f" (período: {min_r.start_date})" if min_r.start_date else ""),
        ]

        # Serie detallada (útil si el LLM necesita ver la tendencia)
        if len(records) <= 24:
            lines.append(f"\nSerie histórica:")
            for r in sorted(records, key=lambda x: x.start_date or ""):
                date_str = r.start_date[:10] if r.start_date else "?"
                lines.append(f"  {date_str}: {r.value:.2f} {unit}")

        return "\n".join(lines)

    def indicator_extremes_narrative(self, records: list[MinMaxIndicatorRecord]) -> str:
        if not records:
            return "No se encontraron extremos históricos de indicadores."
        loc_name = records[0].location_name or f"ubicación {records[0].location_id}"
        lines = [f"Extremos históricos de indicadores — {loc_name}:"]
        for r in records:
            name = r.indicator_name or str(r.indicator_id)
            lines.append(
                f"  • {name}: mín={r.min_value:.2f} ({r.min_date or '?'})"
                f"  |  máx={r.max_value:.2f} ({r.max_date or '?'})"
            )
        return "\n".join(lines)

    def recommendations_narrative(self, features: list[IndicatorFeature]) -> str:
        if not features:
            return "No se encontraron recomendaciones para este indicador en este país."

        recs = [f for f in features if f.type == "recommendation"]
        feats = [f for f in features if f.type == "feature"]

        lines = []
        if recs:
            lines.append("Recomendaciones agronómicas:")
            for r in recs:
                lines.append(f"  • {r.title}")
                if r.description:
                    lines.append(f"    {r.description}")

        if feats:
            lines.append("\nCaracterísticas del indicador:")
            for f in feats:
                lines.append(f"  • {f.title}")
                if f.description:
                    lines.append(f"    {f.description}")

        return "\n".join(lines) if lines else "Sin información adicional."

    def indicators_catalog_summary(self, indicators: list[dict[str, Any]]) -> str:
        if not indicators:
            return "No se encontraron indicadores para este país."
        lines = [f"Indicadores agro-climáticos disponibles ({len(indicators)}):"]
        for ind in indicators:
            name = ind.get("name", "?")
            short = ind.get("short_name", "?")
            unit = ind.get("unit", "?")
            temp = ind.get("temporality", "?")
            itype = ind.get("type", "?")
            lines.append(f"  • [{short}] {name} — {unit} ({temp}, {itype})")
        return "\n".join(lines)
