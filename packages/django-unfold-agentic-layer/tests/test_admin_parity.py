"""MCP writes behave like the admin's own views, end to end through /mcp:
the same ModelAdmin hooks, in the same transaction, refused for the same
reasons (``django/contrib/admin/options.py``: ``_changeform_view``,
``_delete_view``)."""

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth.models import Permission, User
from server.apps.blog.admin import BlogPostAdmin
from server.apps.blog.models import BlogPost

from tests.test_mcp_admin_actions_edge_cases import ACCEPT
from tests.test_mcp_admin_tools import _call_tool, _modern_rpc

POST_ARGUMENTS = {"title": "New", "body": "Body", "status": "draft"}


def _delete(client, tool: str, pk) -> dict:
    """Runs a delete tool through its confirmation round, accepting it."""
    call = {"name": tool, "arguments": {"pk": str(pk)}}
    asked = _modern_rpc(client, "tools/call", call)
    return _modern_rpc(
        client,
        "tools/call",
        {**call, "inputResponses": ACCEPT, "requestState": asked["requestState"]},
    )


@pytest.fixture
def user_deleter(db) -> User:
    """Staff who may delete users — but not the blog posts they authored."""
    user = User.objects.create_user(username="user-deleter", is_staff=True)
    user.user_permissions.set(Permission.objects.filter(codename__in=["view_user", "delete_user"]))
    return user


@pytest.mark.django_db
def test_create_rolls_back_when_a_later_admin_hook_fails(
    client, bearer_login, staff_user, monkeypatch
):
    """save_model ran, save_related failed: like the admin's changeform
    transaction, nothing is left behind."""

    def failing_save_related(self, request, form, formsets, change):
        raise RuntimeError("m2m failed")

    monkeypatch.setattr(BlogPostAdmin, "save_related", failing_save_related)
    bearer_login(client, staff_user)

    result = _modern_rpc(
        client,
        "tools/call",
        {"name": "create_blog_blogpost", "arguments": {**POST_ARGUMENTS, "author": staff_user.pk}},
    )

    assert result["isError"] is True
    assert not BlogPost.objects.exists()


@pytest.mark.django_db
def test_update_rolls_back_when_a_later_admin_hook_fails(
    client, bearer_login, staff_user, monkeypatch
):
    post = BlogPost.objects.create(title="Before", author=staff_user)

    def failing_save_related(self, request, form, formsets, change):
        raise RuntimeError("m2m failed")

    monkeypatch.setattr(BlogPostAdmin, "save_related", failing_save_related)
    bearer_login(client, staff_user)

    result = _modern_rpc(
        client,
        "tools/call",
        {"name": "update_blog_blogpost", "arguments": {"pk": post.pk, "title": "After"}},
    )

    assert result["isError"] is True
    post.refresh_from_db()
    assert post.title == "Before"


@pytest.mark.django_db
def test_delete_refuses_a_cascade_onto_objects_the_user_cannot_delete(
    client, bearer_login, staff_user, user_deleter
):
    author = User.objects.create_user(username="author")
    BlogPost.objects.create(title="Theirs", author=author)
    bearer_login(client, user_deleter)

    result = _delete(client, "delete_auth_user", author.pk)

    assert result["isError"] is True
    assert result["content"][0]["text"] == (
        "Deleting it would also delete blog post, which you do not have permission to delete."
    )
    assert User.objects.filter(pk=author.pk).exists()
    assert BlogPost.objects.filter(author=author).exists()


@pytest.mark.django_db
def test_create_and_update_go_through_the_admin_save_hooks(
    client, bearer_login, staff_user, monkeypatch
):
    calls = []
    for hook in ("save_form", "save_model", "save_related"):
        original = getattr(BlogPostAdmin, hook)

        def spy(self, *args, _hook=hook, _original=original, **kwargs):
            calls.append(_hook)
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(BlogPostAdmin, hook, spy)
    bearer_login(client, staff_user)

    created = _call_tool(
        client, "create_blog_blogpost", {**POST_ARGUMENTS, "author": staff_user.pk}
    )
    _call_tool(client, "update_blog_blogpost", {"pk": created["pk"], "title": "Renamed"})

    assert calls == ["save_form", "save_model", "save_related"] * 2


@pytest.mark.django_db
def test_writes_leave_the_same_history_entries_as_the_admin(client, bearer_login, staff_user):
    bearer_login(client, staff_user)

    created = _call_tool(
        client, "create_blog_blogpost", {**POST_ARGUMENTS, "author": staff_user.pk}
    )
    _call_tool(client, "update_blog_blogpost", {"pk": created["pk"], "title": "Renamed"})
    _delete(client, "delete_blog_blogpost", created["pk"])

    entries = LogEntry.objects.filter(object_id=str(created["pk"])).order_by("pk")
    assert [(e.action_flag, e.user, e.object_repr, e.get_change_message()) for e in entries] == [
        (ADDITION, staff_user, "New", "Added."),
        (CHANGE, staff_user, "Renamed", "Changed Title."),
        (DELETION, staff_user, "Renamed", ""),
    ]
