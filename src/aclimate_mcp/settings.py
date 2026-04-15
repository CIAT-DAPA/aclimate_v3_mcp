"""
AClimate MCP — Configuración
Cargada desde variables de entorno o archivo .env
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ACLIMATE_",
        case_sensitive=False,
    )

    # API v3
    api_base_url: str = "https://api.aclimate.org"
    client_id: str
    client_secret: str

    # MCP
    server_name: str = "AClimate"
    log_level: str = "INFO"


# Instancia global
settings = Settings()  # type: ignore[call-arg]
