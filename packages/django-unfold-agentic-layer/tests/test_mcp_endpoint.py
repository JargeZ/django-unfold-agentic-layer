"""Real end-to-end check that the Django <-> FastMCP bridge actually works.

Drives real MCP JSON-RPC payloads at /mcp/ through Django's normal request
cycle (routing, auth, the MCPView -> bridge.dispatch delegation, and the
StreamableHTTPSessionManager itself) rather than calling bridge.dispatch
in-process. In stateless mode the server-side session starts pre-initialized
(see mcp.server.session.ServerSession.__init__), so a single tools/list
request needs no preceding initialize handshake.
"""

import json

import pytest

MCP_URL = "/mcp/"


def _rpc(client, payload):
    return client.post(
        MCP_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )


@pytest.mark.django_db
def test_tools_list_returns_all_docs_tools_for_staff_user(client, staff_user):
    client.force_login(staff_user)

    response = _rpc(client, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})

    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    # Alongside the static docs tools, staff_user's admin models each also
    # register create/update/delete tools (see test_mcp_admin_resources.py) —
    # filter down to just the docs ones this test is actually about.
    docs_tool_names = {name for name in names if name.startswith("unfold_")}
    assert len(docs_tool_names) == 25
    assert "unfold_get_started" in names


@pytest.mark.django_db
def test_anonymous_request_is_rejected_before_reaching_mcp(client):
    response = _rpc(client, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})

    assert response.status_code == 401


@pytest.mark.django_db
def test_non_staff_request_is_rejected(client, regular_user):
    client.force_login(regular_user)

    response = _rpc(client, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})

    assert response.status_code == 403


@pytest.mark.django_db
def test_unauthorized_dev_mode_acts_as_first_superuser(client, settings, staff_user):
    settings.DEBUG = True
    settings.UNFOLD_AGENTIC_LAYER_UNAUTHORIZED = True

    response = _rpc(client, {"jsonrpc": "2.0", "id": 1, "method": "resources/templates/list", "params": {}})

    assert response.status_code == 200
    # Admin resources only appear for a user with model permissions — proof
    # the request ran as staff_user rather than AnonymousUser.
    assert response.json()["result"]["resourceTemplates"]

    settings.DEBUG = False
    assert _rpc(client, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).status_code == 401
