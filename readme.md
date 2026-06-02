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
AI Clients (Melisa Bot)
        │  MCP Protocol (SSE / Streamable)
        ▼
AClimate MCP Server  ←── FastMCP
        │
AClimate API v3  ←── api.aclimate.org (FastAPI + Keycloak)
        │
PostgreSQL + GeoServer
```
## Resources

### Geo Discovery
| Tool | Descripción |
|------|------------|
| `list_countries` | List all countries in AClimate |
| `list_indicator_categories` | List all categories for indicators |
| `list_indicators` | List all indicators |

## Tools

### Geo Discovery
| Tool | Descripción |
|------|------------|
| `find_admin_region` | Search by administrative level 1 and 2 by name |
| `find_locations` | Search by point of interest for monitoring available → get location_id |

### Historical Climate
| Tool | Descripción |
|------|------------|
| `get_daily_climate` | Historical daily climate data by locations and date range |
| `get_monthly_climate` | Historical monthly climate data by locations and date range. |
| `get_climatology` | Normales climáticas históricas por mes |
| `get_climate_extremes_daily` | Máximos y mínimos históricos absolutos |
| `get_climate_extremes_climatology` | Extremos de climatología por mes |


## Installation

### Requirements
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

# Iniciar el servidor
uv run aclimate-mcp
```

## Variables de entorno

| Variable | Requerida | Default | Descripción |
|----------|-----------|---------|-------------|
| `ACLIMATE_CLIENT_ID` | ✅ | — | Client ID de Keycloak |
| `ACLIMATE_CLIENT_SECRET` | ✅ | — | Client Secret de Keycloak |
| `ACLIMATE_API_BASE_URL` | ❌ | `https://api.aclimate.org` | URL base de la API |
| `ACLIMATE_LOG_LEVEL` | ❌ | `INFO` | Nivel de logging |
| `ACLIMATE_MCP_TRANSPORT` | ✅ | `streamable-http` or `sse` or `stdio` | Modo de ejecución del MCP |
| `ACLIMATE_MCP_HOST` | ✅ | - | Host para correr el servicio |
| `ACLIMATE_MCP_PORT` | ✅ | - | Puerto para correr el servicio |

## Estructura del proyecto

```
aclimate_v3_mcp/
├── src/                        # Source code
│   ├── aclimate_mcp/           # MCP Server
│   │   ├── __init__.py
│   │   ├── prompts.py          # Prompts MCP
│   │   ├── resources.py        # Resources MCP
│   │   ├── server.py           # Run the server for MCP
│   │   ├── settings.py         # Settings via Environmental variables
│   └───└── tools.py            # Tools MCP
├── tests/
│   ├── conftest.py
│   └── test_sdk.py             # Tests unitarios con respx
├── pyproject.toml
├── Dockerfile
├── Jenkins
├── .env.example
└── README.md
```

## Development

```bash
# Tests con cobertura
uv run pytest -v
uv run pytest -v --tb=short

# Linting
uv run ruff check .

# Type checking
uv run mypy aclimate_sdk aclimate_mcp

# Dev
mcp dev "./src/aclimate_mcp/server.py"

```

### Docker (despliegue remoto SSE)

```bash
docker build -t aclimate-mcp .
docker run -p 8000:8000 \
  -e ACLIMATE_CLIENT_ID=tu-id \
  -e ACLIMATE_CLIENT_SECRET=tu-secret \
  aclimate-mcp
```