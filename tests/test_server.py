# tests/test_server.py

import importlib
import sys
import types
from pathlib import Path
import asyncio

import pytest
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_PATH))


SERVER_MODULE_PATH = "aclimate_mcp.server"
# If your file is really at the project root as server.py, change it to:
# SERVER_MODULE_PATH = "server"


class DummySettings:
    log_level = "INFO"
    server_name = "test-aclimate-mcp"
    mcp_host = "127.0.0.1"
    mcp_port = 9000
    mcp_transport = "streamable-http"
    api_base_url = "https://api.example.com"
    client_id = "test-client"
    client_secret = "test-secret"


class DummyMCP:
    def __init__(self, *args, **kwargs):
        self.routes = {}
        self.run_calls = []

    def custom_route(self, path, methods):
        def decorator(func):
            self.routes[path] = {
                "methods": methods,
                "handler": func,
            }
            return func

        return decorator

    def run(self, **kwargs):
        self.run_calls.append(kwargs)


@pytest.fixture
def server_module(monkeypatch):
    """
    Create an isolated server module with all external dependencies mocked.
    This fixture prevents real API calls and avoids starting a real MCP server.
    """
    dummy_mcp = DummyMCP()
    dummy_client = object()

    async def fake_get_client(**kwargs):
        return dummy_client

    def fake_register_resources(**kwargs):
        fake_register_resources.called_with = kwargs

    def fake_register_tools(**kwargs):
        fake_register_tools.called_with = kwargs

    def fake_register_prompts(**kwargs):
        fake_register_prompts.called_with = kwargs

    fake_settings_module = types.ModuleType("aclimate_mcp.settings")
    fake_settings_module.Settings = DummySettings

    fake_resources_module = types.ModuleType("aclimate_mcp.resources")
    fake_resources_module.register_resources = fake_register_resources

    fake_tools_module = types.ModuleType("aclimate_mcp.tools")
    fake_tools_module.register_tools = fake_register_tools

    fake_prompts_module = types.ModuleType("aclimate_mcp.prompts")
    fake_prompts_module.register_prompts = fake_register_prompts

    fake_client_module = types.ModuleType("aclimatesdkpy.aclimate_client")
    fake_client_module.get_client = fake_get_client

    fake_fastmcp_module = types.ModuleType("mcp.server.fastmcp")
    fake_fastmcp_module.FastMCP = lambda *args, **kwargs: dummy_mcp

    monkeypatch.setitem(sys.modules, "aclimate_mcp.settings", fake_settings_module)
    monkeypatch.setitem(sys.modules, "aclimate_mcp.resources", fake_resources_module)
    monkeypatch.setitem(sys.modules, "aclimate_mcp.tools", fake_tools_module)
    monkeypatch.setitem(sys.modules, "aclimate_mcp.prompts", fake_prompts_module)
    monkeypatch.setitem(sys.modules, "aclimatesdkpy.aclimate_client", fake_client_module)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fake_fastmcp_module)

    sys.modules.pop(SERVER_MODULE_PATH, None)

    module = importlib.import_module(SERVER_MODULE_PATH)

    module._dummy_mcp = dummy_mcp
    module._dummy_client = dummy_client
    module._fake_register_resources = fake_register_resources
    module._fake_register_tools = fake_register_tools
    module._fake_register_prompts = fake_register_prompts

    return module


def test_index_returns_html_response(server_module):
    """
    Verify that the index endpoint returns a valid HTML page
    containing the expected MCP server information.
    """
    request = Request({"type": "http", "method": "GET", "path": "/"})

    response = asyncio.run(server_module.index(request))

    assert isinstance(response, HTMLResponse)
    assert response.status_code == 200

    content = response.body.decode("utf-8")

    assert "MCP Running" in content
    assert "AClimate MCP" in content
    assert "/health" in content
    assert "/mcp" in content
    assert "/sse" in content


def test_health_returns_expected_configuration(server_module):
    """
    Verify that the health endpoint returns the expected
    service configuration and status information.
    """
    request = Request({"type": "http", "method": "GET", "path": "/health"})

    response = asyncio.run(server_module.health(request))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 200

    payload = response.body.decode("utf-8")

    assert '"status":"ok"' in payload
    assert '"service":"test-aclimate-mcp"' in payload
    assert '"transport":"streamable-http"' in payload
    assert '"api_base_url":"https://api.example.com"' in payload
    assert '"host":"127.0.0.1"' in payload
    assert '"port":9000' in payload


def test_health_typo_alias_delegates_to_health(server_module):
    """
    Verify that the typo alias endpoint delegates to the
    health endpoint and returns the same successful response.
    """
    request = Request({"type": "http", "method": "GET", "path": "/healt"})

    response = asyncio.run(server_module.health_typo_alias(request))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 200

    payload = response.body.decode("utf-8")

    assert '"status":"ok"' in payload


def test_register_resources_called_with_expected_arguments(server_module):
    """
    Verify that resources are registered using the shared MCP
    instance and the shared client during module initialization.
    """
    assert server_module._fake_register_resources.called_with == {
        "mcp": server_module.mcp,
        "client": server_module._dummy_client,
    }


def test_register_tools_called_with_expected_arguments(server_module):
    """
    Verify that tools are registered using the shared MCP
    instance and the shared client during module initialization.
    """
    assert server_module._fake_register_tools.called_with == {
        "mcp": server_module.mcp,
        "client": server_module._dummy_client,
    }


def test_register_prompts_called_with_expected_arguments(server_module):
    """
    Verify that prompts are registered using the MCP instance
    during module initialization.
    """
    assert server_module._fake_register_prompts.called_with == {
        "mcp": server_module.mcp,
    }


def test_main_uses_streamable_http_transport(server_module):
    """
    Verify that the server starts using the streamable-http
    transport when configured.
    """
    server_module.settings.mcp_transport = "streamable-http"

    server_module.main()

    assert server_module._dummy_mcp.run_calls[-1] == {
        "transport": "streamable-http",
        "mount_path": "/mcp",
    }


def test_main_uses_sse_transport(server_module):
    """
    Verify that the server starts using the SSE transport
    when configured.
    """
    server_module.settings.mcp_transport = "sse"

    server_module.main()

    assert server_module._dummy_mcp.run_calls[-1] == {
        "transport": "sse",
        "mount_path": "/sse",
    }


def test_main_uses_stdio_transport_for_unknown_configuration(server_module):
    """
    Verify that the server falls back to stdio transport
    when the configured transport is not supported.
    """
    server_module.settings.mcp_transport = "unsupported"

    server_module.main()

    assert server_module._dummy_mcp.run_calls[-1] == {
        "transport": "stdio",
    }