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
    assert len(names) == 25
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
