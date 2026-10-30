"""
Prompts:
    - analyze_climate_risk
    - compare_location_climate
"""

from __future__ import annotations


def register_prompts(mcp) -> None:
    @mcp.prompt(
        description=(
            "Guided agroclimatic risk analysis for a crop at one location, "
            "using the AClimate tools in the right order."
        )
    )
    def analyze_climate_risk(location_name: str, crop: str, season: str) -> str:
        return f"""Analyze the climate risk for growing {crop} in {location_name} during {season}.

Follow these steps with the AClimate tools:
1. search_locations_by_name("{location_name}") -> pick the right station and note its location_id and country.
2. get_available_climate_climatology_date_ranges(location_id) and get_available_indicator_date_ranges(location_id) -> learn what data exists before asking for it.
3. get_climatology(location_id, start_month, end_month) with the months of {season} -> the normal climate for the season.
4. get_indicator_history(location_id) -> per-indicator summaries; if one indicator matters most, call it again with its indicator_id.
5. If indicators exist, get_features_indicator(indicator_id, country_id) for management recommendations.
6. Answer citing the station name, the period used, and the units of every figure. If a step returns no data, say so instead of estimating."""

    @mcp.prompt(
        description=(
            "Side-by-side climate comparison of two locations for one "
            "variable, one tool call per location."
        )
    )
    def compare_location_climate(location_a: str, location_b: str, variable: str) -> str:
        return f"""Compare {variable} between {location_a} and {location_b}.

Follow these steps with the AClimate tools:
1. search_locations_by_name for each location -> two location_ids. The summaries collapse per measure, so always query ONE location per call.
2. get_available_climate_monthly_date_ranges for each -> find the overlapping period and check both stations actually serve {variable}.
3. get_monthly_climate(location_id, start_date, end_date) once per location over the SAME period.
4. Compare only the overlapping period, in the same units; note any months missing on either side. If a station does not serve {variable}, say so instead of substituting another variable."""
