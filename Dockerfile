FROM python:3.10-slim

WORKDIR /app

# Instala uv para gestión de dependencias
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copia archivos del proyecto
COPY pyproject.toml .
COPY aclimate_sdk/ ./aclimate_sdk/
COPY aclimate_mcp/ ./aclimate_mcp/

# Instala dependencias (sin dev)
RUN uv sync --no-dev

# Variables de entorno requeridas (pasar en runtime)
ENV ACLIMATE_API_BASE_URL=https://api.aclimate.org
ENV ACLIMATE_LOG_LEVEL=INFO

# Expone puerto SSE (para clientes remotos)
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

CMD ["uv", "run", "aclimate-mcp"]
