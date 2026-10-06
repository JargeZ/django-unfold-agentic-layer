"""Real end-to-end checks that admin models surface create/update/delete
tools through the actual /mcp/ bridge (spec §9/§9.1).

Create/update need nothing special — a plain tools/call request negotiates
fine. Delete's InputRequiredResult confirmation (SEP-2322) only exists on
protocol 2026-07-28+; a stateless connection has no session to carry that
negotiation between requests, so every delete-flow request must carry the
modern envelope itself (see build_model_delete_tool_definition.py and
_modern_rpc below) — a real client library does this automatically, this is
only needed here because these tests speak raw JSON-RPC.
"""

import json

import pytest
from server.apps.blog.models import BlogPost

MCP_URL = "/mcp/"
PROTOCOL_VERSION = "2026-07-28"


def _rpc(client, method, params=None, request_id=1):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    response = client.post(
        MCP_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert "error" not in body, body
    return body["result"]


def _call_tool(client, name, arguments):
    result = _rpc(client, "tools/call", {"name": name, "arguments": arguments})
    return json.loads(result["content"][0]["text"])


def _modern_rpc(client, method, params, request_id=1):
    """Like _rpc, but carries the SEP-2322 modern-protocol envelope every
    request needs in stateless mode: an ``mcp-protocol-version`` header, a
    ``params._meta`` block naming that version + client capabilities, an
    ``mcp-method`` header matching the JSON-RPC method, and — for tools/call
    specifically — an ``mcp-name`` header matching ``params.name``.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
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
        HTTP_MCP_METHOD=method,
        HTTP_MCP_NAME=params.get("name", ""),
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert "error" not in body, body
    return body["result"]


@pytest.mark.django_db
def test_create_tool_creates_instance(client, bearer_login, staff_user):
    bearer_login(client, staff_user)

    result = _call_tool(
        client,
        "create_blog_blogpost",
        {
            "title": "New post",
            "body": "Some body",
            "author": str(staff_user.pk),
            "status": "published",
        },
    )

    assert result["success"] is True, result
    post = BlogPost.objects.get(pk=result["pk"])
    assert post.title == "New post"
    assert post.author_id == staff_user.pk
    assert result["resource_uri"] == f"dj-admin://blog/blogpost/{post.pk}/"


@pytest.mark.django_db
def test_create_tool_reports_validation_errors(client, bearer_login, staff_user):
    bearer_login(client, staff_user)

    # "author" is required and omitted.
    result = _call_tool(client, "create_blog_blogpost", {"title": "Missing author"})

    assert result["success"] is False
    assert "author" in result["errors"]
    assert not BlogPost.objects.filter(title="Missing author").exists()


@pytest.mark.django_db
def test_update_tool_applies_partial_update(client, bearer_login, staff_user):
    post = BlogPost.objects.create(title="Original", body="Original body", author=staff_user)
    bearer_login(client, staff_user)

    result = _call_tool(
        client, "update_blog_blogpost", {"pk": str(post.pk), "body": "Updated body"}
    )

    assert result["success"] is True
    post.refresh_from_db()
    assert post.title == "Original"  # untouched
    assert post.body == "Updated body"


@pytest.mark.django_db
def test_delete_tool_requires_confirmation_then_deletes(client, bearer_login, staff_user):
    post = BlogPost.objects.create(title="ToDelete", author=staff_user)
    bearer_login(client, staff_user)

    first = _modern_rpc(
        client, "tools/call", {"name": "delete_blog_blogpost", "arguments": {"pk": str(post.pk)}}
    )
    assert "inputRequests" in first
    assert BlogPost.objects.filter(pk=post.pk).exists()

    second = _modern_rpc(
        client,
        "tools/call",
        {
            "name": "delete_blog_blogpost",
            "arguments": {"pk": str(post.pk)},
            "inputResponses": {"confirm": {"action": "accept", "content": {"confirmed": True}}},
            "requestState": first["requestState"],
        },
    )
    assert second["content"][0]["text"] == f"Deleted blog post (pk={post.pk})."
    assert not BlogPost.objects.filter(pk=post.pk).exists()


@pytest.mark.django_db
def test_delete_tool_cancelled_keeps_instance(client, bearer_login, staff_user):
    post = BlogPost.objects.create(title="KeepMe", author=staff_user)
    bearer_login(client, staff_user)

    first = _modern_rpc(
        client, "tools/call", {"name": "delete_blog_blogpost", "arguments": {"pk": str(post.pk)}}
    )

    second = _modern_rpc(
        client,
        "tools/call",
        {
            "name": "delete_blog_blogpost",
            "arguments": {"pk": str(post.pk)},
            "inputResponses": {"confirm": {"action": "accept", "content": {"confirmed": False}}},
            "requestState": first["requestState"],
        },
    )
    assert second["content"][0]["text"] == "Deletion cancelled."
    assert BlogPost.objects.filter(pk=post.pk).exists()


@pytest.mark.django_db
def test_staff_user_without_permissions_has_no_crud_tools(
    client, bearer_login, staff_user_without_permissions
):
    bearer_login(client, staff_user_without_permissions)

    result = _rpc(client, "tools/list")

    crud_tool_names = {t["name"] for t in result["tools"] if not t["name"].startswith("unfold_")}
    assert crud_tool_names == set()


@pytest.mark.django_db
def test_broken_model_admin_is_skipped_not_fatal(client, bearer_login, staff_user, monkeypatch):
    from django.contrib import admin
    from django.core.exceptions import FieldError

    def broken_get_form(*args, **kwargs):
        raise FieldError("Unknown field(s) (password1, password2) specified for User")

    monkeypatch.setattr(admin.site._registry[BlogPost], "get_form", broken_get_form)
    bearer_login(client, staff_user)

    names = {tool["name"] for tool in _rpc(client, "tools/list")["tools"]}

    assert "create_blog_blogpost" not in names
    assert "create_auth_user" in names
