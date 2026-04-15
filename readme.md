# AClimate MCP Server


MCP server exposing the [AClimate API v3](https://api.aclimate.org/docs) 
to the AI ​​ecosystem. It allows agents to reason about historical 
agro-climatic data, risk indicators, and recommendations directly from a conversation.

## 🏷️ Version & Tags

**Current version:** `v0.1.0`  
**Tags:** `aclimate`, `mcp`, `python`, `agent-ai`, `climate`, `agriculture`

---
## Architecture

```
AI Clients (Claude, Claude Code, Melisa Bot)
        │  MCP Protocol (stdio / SSE)
        ▼
AClimate MCP Server  ←── FastMCP
        │
AClimate Python SDK  ←── httpx async + Pydantic v2 + Cache
        │
AClimate API v3  ←── api.aclimate.org (FastAPI + Keycloak)
        │
PostgreSQL + GeoServer
```

## Tools disponibles

### Geo Discovery
| Tool | Descripción |
|------|------------|
| `list_countries` | Lista todos los países en AClimate |
| `find_country_by_name` | Busca país por nombre → obtiene country_id |
| `find_admin_region` | Busca departamentos/municipios por nombre |
| `find_locations` | Busca estaciones de monitoreo → obtiene location_id |
| `get_locations_with_current_data` | Condiciones actuales por país |
| `get_point_data_from_coordinates` | Datos raster para lat/lon arbitrarios |

### Historical Climate
| Tool | Descripción |
|------|------------|
| `get_daily_climate` | Serie diaria por ubicación y medidas |
| `get_monthly_climate` | Serie mensual por ubicación |
| `get_climatology` | Normales climáticas históricas por mes |
| `get_climate_extremes_daily` | Máximos y mínimos históricos absolutos |
| `get_climate_extremes_climatology` | Extremos de climatología por mes |

### Agro-climate Indicators
| Tool | Descripción |
|------|------------|
| `list_indicators_by_country` | Catálogo de indicadores (CRD, heat_stress...) |
| `get_indicator_history` | Historial de todos los indicadores de una ubicación |
| `get_indicator_by_name_and_location` | Indicador específico por nombre y lugar |
| `get_indicator_by_period` | Indicador filtrado por fecha y período |
| `get_indicator_extremes` | Peores valores históricos de indicadores |
| `get_agro_recommendations` | Recomendaciones CIAT para un indicador |
| `list_indicator_categories` | Categorías: Heat Stress, Precipitation, etc. |

## Instalación

### Requisitos
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recomendado) o pip

### Setup

```bash
# Clonar el repositorio
git clone https://github.com/CIAT-DAPA/aclimate_v3_mcp
cd aclimate_v3_mcp

# Instalar dependencias
source .venv/bin/activate # Linux
.venv\Scripts\activate # Windows
uv sync

# Configurar credenciales
cp .env.example .env
# Editar .env con tu client_id y client_secret de Keycloak

# Correr Web de test
mcp dev "./src/aclimate_mcp/server.py"

# Ejecutar tests
uv run pytest -v

# Iniciar el servidor
uv run aclimate-mcp
```

### Claude Desktop

Agrega a `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "aclimate": {
      "command": "uv",
      "args": ["run", "aclimate-mcp"],
      "cwd": "/ruta/a/aclimate-mcp",
      "env": {
        "ACLIMATE_CLIENT_ID": "tu-client-id",
        "ACLIMATE_CLIENT_SECRET": "tu-client-secret"
      }
    }
  }
}
```

## Variables de entorno

| Variable | Requerida | Default | Descripción |
|----------|-----------|---------|-------------|
| `ACLIMATE_CLIENT_ID` | ✅ | — | Client ID de Keycloak |
| `ACLIMATE_CLIENT_SECRET` | ✅ | — | Client Secret de Keycloak |
| `ACLIMATE_API_BASE_URL` | ❌ | `https://api.aclimate.org` | URL base de la API |
| `ACLIMATE_LOG_LEVEL` | ❌ | `INFO` | Nivel de logging |

## Estructura del proyecto

```
aclimate_v3_mcp/
├── src/                        # Source code
│   ├── aclimate_sdk/           # SDK interno — cliente, modelos, caché
│   │   ├── __init__.py
│   │   ├── client.py           # AClimateClient (httpx async + Keycloak)
│   │   ├── models.py           # Modelos Pydantic del spec openapi.json
│   │   ├── context_builder.py  # Transformación datos → narrativa IA
│   │   └── cache.py            # CacheLayer (Redis / in-memory)
│   ├── aclimate_mcp/           # MCP Server
│   │   ├── __init__.py
│   │   ├── server.py           # Tools, Resources y Prompts MCP
│   └───└── settings.py         # Configuración via env vars
├── tests/
│   ├── conftest.py
│   └── test_sdk.py             # Tests unitarios con respx
├── pyproject.toml
├── Dockerfile
├── .env.example
└── README.md
```

## Desarrollo

```bash
# Tests con cobertura
uv run pytest -v --tb=short

# Linting
uv run ruff check .

# Type checking
uv run mypy aclimate_sdk aclimate_mcp
```

### Docker (despliegue remoto SSE)

```bash
docker build -t aclimate-mcp .
docker run -p 8000:8000 \
  -e ACLIMATE_CLIENT_ID=tu-id \
  -e ACLIMATE_CLIENT_SECRET=tu-secret \
  aclimate-mcp
```