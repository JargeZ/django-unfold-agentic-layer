"""CONFIRM_WRITES: every data-changing tool asks the user first, through the
same confirmation round as delete tools and DANGER actions."""

import json

import pytest
from server.apps.blog.models import BlogPost

from tests.test_mcp_admin_actions_edge_cases import ACCEPT
from tests.test_mcp_admin_tools import _call_tool, _modern_rpc

DECLINE = {"confirm": {"action": "decline"}}


@pytest.fixture
def confirm_writes(settings):
    settings.UNFOLD_AGENTIC_LAYER = {"CONFIRM_WRITES": True}


@pytest.fixture
def post(staff_user) -> BlogPost:
    return BlogPost.objects.create(title="Before", author=staff_user)


def _answer(client, call: dict, asked: dict, answer: dict) -> dict:
    return _modern_rpc(
        client,
        "tools/call",
        {**call, "inputResponses": answer, "requestState": asked["requestState"]},
    )


def _result(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


def _question(asked: dict) -> str:
    return asked["inputRequests"]["confirm"]["params"]["message"]


@pytest.mark.django_db
@pytest.mark.usefixtures("confirm_writes")
def test_create_asks_before_saving(client, bearer_login, staff_user):
    bearer_login(client, staff_user)
    call = {
        "name": "create_blog_blogpost",
        "arguments": {"title": "New", "status": "draft", "author": staff_user.pk},
    }

    asked = _modern_rpc(client, "tools/call", call)

    assert _question(asked) == (
        f"Create blog post (title='New', author={staff_user.pk}, status='draft')?"
    )
    assert not BlogPost.objects.exists()
    assert _result(_answer(client, call, asked, ACCEPT))["success"] is True
    assert BlogPost.objects.get().title == "New"


@pytest.mark.django_db
@pytest.mark.usefixtures("confirm_writes")
def test_declined_update_changes_nothing(client, bearer_login, staff_user, post):
    bearer_login(client, staff_user)
    call = {"name": "update_blog_blogpost", "arguments": {"pk": post.pk, "title": "After"}}

    asked = _modern_rpc(client, "tools/call", call)
    declined = _result(_answer(client, call, asked, DECLINE))

    assert _question(asked) == f"Update blog post Before (pk={post.pk}): title='After'?"
    assert declined["errors"]["__all__"][0]["code"] == "cancelled"
    post.refresh_from_db()
    assert post.title == "Before"


@pytest.mark.django_db
@pytest.mark.usefixtures("confirm_writes")
def test_confirmed_update_saves(client, bearer_login, staff_user, post):
    bearer_login(client, staff_user)
    call = {"name": "update_blog_blogpost", "arguments": {"pk": post.pk, "title": "After"}}

    asked = _modern_rpc(client, "tools/call", call)

    assert _result(_answer(client, call, asked, ACCEPT))["success"] is True
    post.refresh_from_db()
    assert post.title == "After"


@pytest.mark.django_db
@pytest.mark.usefixtures("confirm_writes")
def test_invalid_input_is_reported_without_asking(client, bearer_login, staff_user):
    bearer_login(client, staff_user)

    result = _modern_rpc(
        client, "tools/call", {"name": "create_blog_blogpost", "arguments": {"title": "No author"}}
    )

    assert "inputRequests" not in result
    assert "author" in _result(result)["errors"]


@pytest.mark.django_db
@pytest.mark.usefixtures("confirm_writes")
def test_plain_actions_ask_too(client, bearer_login, staff_user, post):
    bearer_login(client, staff_user)
    call = {"name": "run_blog_blogpost_publish_posts", "arguments": {"pks": [post.pk]}}

    asked = _modern_rpc(client, "tools/call", call)

    assert "inputRequests" in asked
    post.refresh_from_db()
    assert post.status == "draft"
    _answer(client, call, asked, ACCEPT)
    post.refresh_from_db()
    assert post.status == "published"


@pytest.mark.django_db
def test_writes_run_directly_by_default(client, bearer_login, staff_user, post):
    bearer_login(client, staff_user)

    result = _call_tool(client, "update_blog_blogpost", {"pk": post.pk, "title": "After"})

    assert result["success"] is True
