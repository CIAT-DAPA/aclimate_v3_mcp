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
    language = "es"


class DummyMCP:
    def __init__(self, *args, **kwargs):
        self.routes = {}
        self.run_calls = []
        self.lifespan = kwargs.get("lifespan")

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

    async def fake_close_client():
        fake_close_client.called = True

    fake_close_client.called = False

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
    fake_client_module.close_client = fake_close_client
    fake_client_module.AClimateClient = object

    class FakeContextBuilder:
        def __init__(self, language="en"):
            self.language = language

    fake_context_module = types.ModuleType("aclimatesdkpy.context_builder")
    fake_context_module.ContextBuilder = FakeContextBuilder

    fake_fastmcp_module = types.ModuleType("mcp.server.fastmcp")

    def fake_fastmcp(*args, **kwargs):
        dummy_mcp.lifespan = kwargs.get("lifespan")
        return dummy_mcp

    fake_fastmcp_module.FastMCP = fake_fastmcp

    monkeypatch.setitem(sys.modules, "aclimate_mcp.settings", fake_settings_module)
    monkeypatch.setitem(sys.modules, "aclimate_mcp.resources", fake_resources_module)
    monkeypatch.setitem(sys.modules, "aclimate_mcp.tools", fake_tools_module)
    monkeypatch.setitem(sys.modules, "aclimate_mcp.prompts", fake_prompts_module)
    monkeypatch.setitem(sys.modules, "aclimatesdkpy.aclimate_client", fake_client_module)
    monkeypatch.setitem(sys.modules, "aclimatesdkpy.context_builder", fake_context_module)
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
        "get_client": server_module.provide_client,
    }


def test_register_tools_called_with_expected_arguments(server_module):
    """
    Verify that tools are registered using the shared MCP
    instance and the shared client during module initialization.
    """
    kwargs = server_module._fake_register_tools.called_with
    assert kwargs["mcp"] is server_module.mcp
    assert kwargs["get_client"] is server_module.provide_client
    assert kwargs["ctx"] is server_module.context_builder
    assert kwargs["ctx"].language == "es"


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


def test_provide_client_resolves_the_shared_client(server_module):
    """
    Verify that the provider resolves the shared client inside a running
    event loop, so the HTTP pool belongs to the loop serving the requests.
    """
    assert asyncio.run(server_module.provide_client()) is server_module._dummy_client


def test_module_declares_no_lifespan(server_module):
    """
    Under streamable-http/sse FastMCP runs the lifespan once per MCP session,
    so the process-wide client must not be torn down there.
    """
    assert not hasattr(server_module, "lifespan")


def test_client_is_not_created_at_import_time(server_module):
    """
    Verify that importing the module does not open the HTTP client,
    so the connection pool stays bound to the serving event loop.
    """
    assert not hasattr(server_module, "client")