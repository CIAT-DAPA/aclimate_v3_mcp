# AClimate MCP Server
#
#   docker build -t aclimate-mcp .
#   docker run -p 8000:8000 \
#     -e ACLIMATE_CLIENT_ID=your-id \
#     -e ACLIMATE_CLIENT_SECRET=your-secret \
#     aclimate-mcp
#
FROM python:3.10-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# git: aclimatesdkpy is installed from a git ref (see [tool.uv.sources]).
# curl: used by the container HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so a source-only change does not re-resolve the tree.
COPY pyproject.toml uv.lock readme.md ./
COPY src ./src
RUN uv sync --no-dev --frozen

ENV PATH="/app/.venv/bin:$PATH"

# Defaults so `docker run` works with only the credentials supplied.
# Settings has no defaults for transport/host/port, so they must be set here.
ENV ACLIMATE_API_BASE_URL=https://api.aclimate.org \
    ACLIMATE_LOG_LEVEL=INFO \
    ACLIMATE_MCP_TRANSPORT=streamable-http \
    ACLIMATE_MCP_HOST=0.0.0.0 \
    ACLIMATE_MCP_PORT=8000

RUN useradd --create-home --uid 10001 mcp && chown -R mcp:mcp /app
USER mcp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${ACLIMATE_MCP_PORT}/health" || exit 1

CMD ["aclimate-mcp"]
