"""Real end-to-end checks that every Unfold admin action kind is exposed as
a ``run_*`` tool through the actual /mcp bridge: bulk (Django ``actions``,
incl. ``action_form`` extras and a DANGER variant), ``actions_list``,
``actions_row`` and ``actions_detail`` (incl. dialog forms and dropdown
groups). ``actions_submit_line`` and Django's ``delete_selected`` are
deliberately not exposed (see ExtractActionTools).
"""

import pytest
from server.apps.blog.models import BlogPost

from tests.test_mcp_admin_tools import _call_tool, _modern_rpc, _rpc


def _run_tools(client):
    return {
        t["name"]: t for t in _rpc(client, "tools/list")["tools"] if t["name"].startswith("run_")
    }


def _call(client, name, arguments):
    """A tools/call that's allowed to fail at the tool level (``isError``)."""
    return _rpc(client, "tools/call", {"name": name, "arguments": arguments})


@pytest.mark.django_db
def test_every_action_kind_becomes_a_tool_with_its_form_as_parameters(
    client, bearer_login, staff_user, snapshot
):
    bearer_login(client, staff_user)

    tools = _run_tools(client)

    # Not exposed: Django's bulk delete (the delete tool covers it) and the
    # submit-line action (runs inside save_model, not standalone).
    assert "run_blog_blogpost_delete_selected" not in tools
    assert "run_blog_blogpost_notify_author_on_save" not in tools
    assert [
        {"name": name, "description": tool["description"], "inputSchema": tool["inputSchema"]}
        for name, tool in tools.items()
    ] == snapshot


@pytest.mark.django_db
def test_bulk_actions_run_on_selected_pks_with_action_form_fields(client, bearer_login, staff_user):
    selected = BlogPost.objects.create(title="Selected", author=staff_user)
    other = BlogPost.objects.create(title="Other", author=staff_user)
    bearer_login(client, staff_user)

    result = _call_tool(client, "run_blog_blogpost_publish_posts", {"pks": [str(selected.pk)]})

    assert result == {
        "success": True,
        "messages": [{"level": "success", "message": "Published 1 post(s)."}],
        "returned_page": False,
    }
    selected.refresh_from_db()
    other.refresh_from_db()
    assert (selected.status, other.status) == ("published", "draft")

    # action_form's extra "editor" field reaches the action through request.POST.
    _call_tool(
        client,
        "run_blog_blogpost_assign_editor",
        {"pks": [str(selected.pk)], "editor": str(staff_user.pk)},
    )
    selected.refresh_from_db()
    assert selected.editor == staff_user

    invalid = _call_tool(
        client, "run_blog_blogpost_assign_editor", {"pks": [str(selected.pk)], "editor": "999"}
    )
    assert invalid["success"] is False
    assert "editor" in invalid["errors"]

    nothing_selected = _call_tool(client, "run_blog_blogpost_publish_posts", {"pks": []})
    assert "pks" in nothing_selected["errors"]


@pytest.mark.django_db
def test_danger_action_asks_for_confirmation(client, bearer_login, staff_user):
    post = BlogPost.objects.create(title="Archive me", author=staff_user)
    bearer_login(client, staff_user)
    call = {"name": "run_blog_blogpost_archive_selected", "arguments": {"pks": [str(post.pk)]}}

    first = _modern_rpc(client, "tools/call", call)
    assert "inputRequests" in first

    declined = _modern_rpc(
        client,
        "tools/call",
        {
            **call,
            "inputResponses": {"confirm": {"action": "decline"}},
            "requestState": first["requestState"],
        },
    )
    assert declined["structuredContent"]["success"] is False
    post.refresh_from_db()
    assert post.status == "draft"

    # Each confirmation round's state is single-use, so accepting needs a fresh one.
    second = _modern_rpc(client, "tools/call", call)
    accepted = _modern_rpc(
        client,
        "tools/call",
        {
            **call,
            "inputResponses": {"confirm": {"action": "accept", "content": {"confirmed": True}}},
            "requestState": second["requestState"],
        },
    )
    assert accepted["structuredContent"]["messages"] == [
        {"level": "warning", "message": "Archived 1 post(s)."}
    ]
    post.refresh_from_db()
    assert post.status == "archived"


@pytest.mark.django_db
def test_list_actions_return_files_and_validate_dialog_forms(client, bearer_login, staff_user):
    BlogPost.objects.create(title="Exported", author=staff_user)
    bearer_login(client, staff_user)

    export = _call(client, "run_blog_blogpost_export_all_posts", {})
    resource = export["content"][1]["resource"]
    assert export["structuredContent"]["file"] == {
        "filename": "posts.csv",
        "content_type": "text/csv",
        "size": len(resource["text"].encode()),
    }
    assert resource["mimeType"] == "text/csv"
    assert resource["text"].splitlines() == [
        "id,title,status",
        f"{BlogPost.objects.get().pk},Exported,draft",
    ]

    missing_title = _call_tool(client, "run_blog_blogpost_create_draft", {})
    assert missing_title["success"] is False
    assert "title" in missing_title["errors"]

    created = _call_tool(client, "run_blog_blogpost_create_draft", {"title": "From an agent"})
    draft = BlogPost.objects.get(title="From an agent")
    assert draft.author == staff_user
    assert created["redirect_url"] == f"/admin/blog/blogpost/{draft.pk}/change/"


@pytest.mark.django_db
def test_row_and_detail_actions_run_on_one_instance(client, bearer_login, staff_user):
    post = BlogPost.objects.create(title="Post", body="Body", author=staff_user)
    bearer_login(client, staff_user)
    pk = str(post.pk)

    assert (
        _call_tool(client, "run_blog_blogpost_feature_post", {"pk": pk})["messages"][0]["message"]
        == "Post featured."
    )
    _call_tool(client, "run_blog_blogpost_set_status", {"pk": pk, "status": "archived"})
    _call_tool(client, "run_blog_blogpost_append_note", {"pk": pk, "note": "Reviewed."})
    post.refresh_from_db()
    assert (post.is_featured, post.status, post.body) == (True, "archived", "Body\n\nReviewed.")

    # Choice fields are typed as Literal, so MCP rejects a bad value up front.
    assert (
        _call(client, "run_blog_blogpost_set_status", {"pk": pk, "status": "bogus"})["isError"]
        is True
    )
    assert _call(client, "run_blog_blogpost_feature_post", {"pk": "999"})["isError"] is True


@pytest.mark.django_db
def test_action_tools_follow_admin_permissions(
    client, bearer_login, blog_editor, staff_user_without_permissions
):
    bearer_login(client, blog_editor)
    editor_tools = _run_tools(client)
    # has_publish_permission is superuser-only; everything else is visible.
    assert "run_blog_blogpost_publish_post" not in editor_tools
    assert "run_blog_blogpost_feature_post" in editor_tools

    bearer_login(client, staff_user_without_permissions)
    assert _run_tools(client) == {}
