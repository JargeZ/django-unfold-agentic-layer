"""The final MCP contract suite: drives one full agent session — auth
handshake, tool/resource discovery, docs lookup, and a full create -> read
(detail + list) -> update -> delete-with-confirmation lifecycle — through the
real ``/mcp/`` endpoint on the test app, and freezes every response body with
a syrupy snapshot (see CLAUDE.md's testing conventions / the ``test`` skill:
snapshots are the default for API response assertions).

``_normalize_contract`` replaces every dynamic object pk (a bare JSON "pk"
field, a pk-shaped path segment in a ``dj-admin://`` resource URI, or the
delete flow's "pk=<N>" confirmation message) with a stable placeholder —
structurally, by shape, not by recording a specific pk value up front. A
value-keyed map (e.g. ``{staff_user.pk: "author"}``) would collide as soon as
two unrelated models' first rows land on the same autoincrement value in a
fresh test transaction (a real, observed failure here: a freshly created
``User`` and the first ``BlogPost`` both start at pk=1). It also expands any
string that is itself embedded JSON, since MCP wraps resource/tool payloads
as JSON text inside "text" fields — snapshotting the parsed structure reads
better than an opaque blob.
"""

import json
import re
from typing import Any

import pytest
from server.apps.blog.models import BlogPost
from syrupy.filters import props

MCP_URL = "/mcp/"
PROTOCOL_VERSION = "2026-07-28"
_URI_PK = re.compile(r"(dj-admin://[\w.]+/[\w.]+/)\d+(/)")
_PK_KWARG = re.compile(r"pk=\d+")


def _rpc(client, method, params=None, request_id=1):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    return client.post(
        MCP_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )


def _call_tool(client, name, arguments):
    response = _rpc(client, "tools/call", {"name": name, "arguments": arguments})
    assert response.status_code == 200, response.content
    return response.json()["result"]


def _call_tool_modern(client, name, arguments, extra_params=None):
    """Like ``_call_tool``, but carries the SEP-2322 modern-protocol envelope
    the delete tool's ``InputRequiredResult`` confirmation needs in stateless
    mode (see test_mcp_admin_tools.py's ``_modern_rpc``)."""
    params = {"name": name, "arguments": arguments, **(extra_params or {})}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            **params,
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }
    response = client.post(
        MCP_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
        HTTP_MCP_PROTOCOL_VERSION=PROTOCOL_VERSION,
        HTTP_MCP_METHOD="tools/call",
        HTTP_MCP_NAME=name,
    )
    assert response.status_code == 200, response.content
    return response.json()["result"]


def _normalize_contract(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: "<pk>" if k == "pk" and isinstance(v, (int, str)) else _normalize_contract(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_normalize_contract(v) for v in value]
    if isinstance(value, str):
        if value[:1] in "{[":
            try:
                return _normalize_contract(json.loads(value))
            except ValueError:
                pass
        return _PK_KWARG.sub("pk=<pk>", _URI_PK.sub(r"\1<pk>\2", value))
    return value


@pytest.mark.django_db
def test_full_mcp_contract_lifecycle(client, bearer_login, staff_user, snapshot, freezer):
    """One flowing story, per the ``test`` skill's guidance for a regression
    that's really a single narrative: log in, discover the docs + dynamic
    admin surface, look up a doc, then create/read/update/delete a real
    ``BlogPost`` through the tools and resources that surface generates."""
    freezer.move_to("2026-01-15T12:00:00+00:00")
    bearer_login(client, staff_user)

    tools = _rpc(client, "tools/list").json()
    assert tools["result"] == snapshot(name="tools-list")

    templates = _rpc(client, "resources/templates/list").json()
    assert _normalize_contract(templates["result"]) == snapshot(name="resource-templates-list")

    doc = _call_tool(client, "unfold_get_started", {})
    assert doc == snapshot(name="docs-tool-call")

    created = _call_tool(
        client,
        "create_blog_blogpost",
        {
            "title": "Hello contract",
            "body": "Body text",
            "author": str(staff_user.pk),
            "status": "published",
        },
    )
    assert _normalize_contract(created) == snapshot(name="create-tool-call")
    post = BlogPost.objects.get(pk=json.loads(created["content"][0]["text"])["pk"])

    detail = _rpc(client, "resources/read", {"uri": f"dj-admin://blog/blogpost/{post.pk}/"}).json()
    assert _normalize_contract(detail["result"]) == snapshot(name="read-detail-resource")

    listing = _rpc(client, "resources/read", {"uri": "dj-admin://blog/blogpost/"}).json()
    assert _normalize_contract(listing["result"]) == snapshot(name="read-list-resource")

    updated = _call_tool(
        client, "update_blog_blogpost", {"pk": str(post.pk), "title": "Updated contract"}
    )
    assert _normalize_contract(updated) == snapshot(name="update-tool-call")

    delete_request = _call_tool_modern(client, "delete_blog_blogpost", {"pk": str(post.pk)})
    # requestState is an opaque, randomly-keyed continuation token (differs
    # every call even for the same pk) — assert its shape, snapshot the rest.
    assert isinstance(delete_request["requestState"], str) and delete_request["requestState"]
    assert _normalize_contract(delete_request) == snapshot(
        name="delete-tool-call-confirmation", exclude=props("requestState")
    )

    delete_confirmed = _call_tool_modern(
        client,
        "delete_blog_blogpost",
        {"pk": str(post.pk)},
        extra_params={
            "inputResponses": {"confirm": {"action": "accept", "content": {"confirmed": True}}},
            "requestState": delete_request["requestState"],
        },
    )
    assert _normalize_contract(delete_confirmed) == snapshot(name="delete-tool-call-confirmed")
    assert not BlogPost.objects.filter(pk=post.pk).exists()


@pytest.mark.django_db
def test_unauthenticated_and_forbidden_contract(client, bearer_login, regular_user, snapshot):
    """The auth gate's own response contract (spec: 401 anonymous, 403
    non-staff — plain JSON, no login redirect) — a real client can't follow a
    redirect, so this shape is as much a "contract" as the MCP payloads."""
    anonymous = _rpc(client, "tools/list")
    assert (anonymous.status_code, anonymous.json()) == snapshot(name="anonymous")

    bearer_login(client, regular_user)
    non_staff = _rpc(client, "tools/list")
    assert (non_staff.status_code, non_staff.json()) == snapshot(name="non-staff")
