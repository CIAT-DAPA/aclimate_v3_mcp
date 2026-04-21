from __future__ import annotations


def register_prompts(mcp) -> None:
    @mcp.prompt()
    def analyze_climate_risk(location_name: str, crop: str, season: str) -> str:
        return f"""Realiza un análisis de riesgo climático para el cultivo de {crop}
        en {location_name} durante {season}.

        1. find_locations
        2. get_climatology
        3. indicadores
        4. extremos
        5. recomendaciones
        """

    @mcp.prompt()
    def compare_location_climate(location_a: str, location_b: str, variable: str) -> str:
        return f"""Compara {variable} entre {location_a} y {location_b}."""