"""Edge cases of the ``run_*`` admin action tools, end to end through /mcp/.

Pins down the QA pass over every BlogPostAdmin action: what already works
(regression guards), the bugs that were fixed (F1–F3), and the known ones
still open, written as their *expected* behavior under ``xfail(strict=True)``
— once one is fixed its test XPASSes, which fails the run as a reminder to
drop the marker.
"""

import json

import pytest
from server.apps.blog.models import BlogPost

from tests.test_mcp_admin_actions import _call, _run_tools
from tests.test_mcp_admin_tools import PROTOCOL_VERSION, _call_tool, _modern_rpc

MISSING_PK = "99999"
ACCEPT = {"confirm": {"action": "accept", "content": {"confirmed": True}}}


def _modern_raw(client, params):
    """A modern-protocol tools/call that may fail at the JSON-RPC level —
    returns ``(status_code, body)`` instead of asserting success."""
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
        "/mcp/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
        HTTP_MCP_PROTOCOL_VERSION=PROTOCOL_VERSION,
        HTTP_MCP_METHOD="tools/call",
        HTTP_MCP_NAME=params["name"],
    )
    return response.status_code, response.json()


def _answer(client, call, input_responses, request_state):
    status, body = _modern_raw(
        client, {**call, "inputResponses": input_responses, "requestState": request_state}
    )
    assert status == 200, body
    return body["result"]


@pytest.fixture
def post(staff_user) -> BlogPost:
    return BlogPost.objects.create(title="Post", body="Body", author=staff_user)


@pytest.fixture
def other_post(staff_user) -> BlogPost:
    return BlogPost.objects.create(title="Other", author=staff_user)


@pytest.fixture
def logged_in(client, bearer_login, staff_user):
    bearer_login(client, staff_user)
    return client


# --- instance actions (actions_row / actions_detail) -------------------------


@pytest.mark.django_db
def test_feature_post_is_idempotent(logged_in, post):
    for _ in range(2):
        result = _call_tool(logged_in, "run_blog_blogpost_feature_post", {"pk": str(post.pk)})
        assert result == {
            "success": True,
            "messages": [{"level": "success", "message": "Post featured."}],
            "redirect_url": "/admin/blog/blogpost/",
            "returned_page": False,
        }
    post.refresh_from_db()
    assert post.is_featured is True


@pytest.mark.django_db
@pytest.mark.parametrize("pk", [MISSING_PK, "abc", "", "1.5"])
@pytest.mark.parametrize(
    ("tool", "extra"),
    [
        ("run_blog_blogpost_feature_post", {}),
        ("run_blog_blogpost_publish_post", {}),
        ("run_blog_blogpost_append_note", {"note": "x"}),
        ("run_blog_blogpost_set_status", {"status": "draft"}),
    ],
)
def test_instance_action_on_unknown_pk_is_a_tool_error(logged_in, tool, extra, pk):
    result = _call(logged_in, tool, {"pk": pk, **extra})
    assert result["isError"] is True
    assert f"No blog post found with pk={pk!r}" in result["content"][0]["text"]


@pytest.mark.django_db
def test_publish_post_redirects_to_the_change_page(logged_in, post):
    result = _call_tool(logged_in, "run_blog_blogpost_publish_post", {"pk": str(post.pk)})
    assert result["redirect_url"] == f"/admin/blog/blogpost/{post.pk}/change/"
    post.refresh_from_db()
    assert post.status == "published"


@pytest.mark.django_db
def test_append_note_appends_verbatim(logged_in, post, other_post):
    script = '<script>alert(1)</script> & "x"'
    _call_tool(logged_in, "run_blog_blogpost_append_note", {"pk": str(post.pk), "note": "Note ✅"})
    _call_tool(logged_in, "run_blog_blogpost_append_note", {"pk": str(post.pk), "note": script})
    # An empty body gets no leading blank lines.
    _call_tool(
        logged_in, "run_blog_blogpost_append_note", {"pk": str(other_post.pk), "note": "One"}
    )

    post.refresh_from_db()
    other_post.refresh_from_db()
    assert post.body == f"Body\n\nNote ✅\n\n{script}"
    assert other_post.body == "One"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("tool", "arguments", "field", "code"),
    [
        ("run_blog_blogpost_append_note", {}, "note", "required"),
        ("run_blog_blogpost_append_note", {"note": ""}, "note", "required"),
        ("run_blog_blogpost_append_note", {"note": "   "}, "note", "required"),
        ("run_blog_blogpost_set_status", {}, "status", "required"),
        ("run_blog_blogpost_create_draft", {}, "title", "required"),
        ("run_blog_blogpost_create_draft", {"title": ""}, "title", "required"),
        ("run_blog_blogpost_create_draft", {"title": "y" * 300}, "title", "max_length"),
    ],
)
def test_dialog_form_errors_are_structured(logged_in, post, tool, arguments, field, code):
    if tool != "run_blog_blogpost_create_draft":
        arguments = {"pk": str(post.pk), **arguments}
    result = _call_tool(logged_in, tool, arguments)
    assert result["success"] is False
    assert [error["code"] for error in result["errors"][field]] == [code]
    assert BlogPost.objects.count() == 1  # nothing created, nothing else touched


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("run_blog_blogpost_set_status", {"status": "deleted"}),
        ("run_blog_blogpost_set_status", {"status": "Published"}),  # enum is case-sensitive
        ("run_blog_blogpost_set_status", {"status": "draft", "bogus": 1}),
        ("run_blog_blogpost_feature_post", {"pk": 1}),  # pk must be a string
    ],
)
def test_arguments_outside_the_schema_are_rejected(logged_in, post, tool, arguments):
    arguments = {"pk": str(post.pk), **arguments}
    assert _call(logged_in, tool, arguments)["isError"] is True
    post.refresh_from_db()
    assert (post.status, post.is_featured) == ("draft", False)


# --- bulk actions (Django ``actions`` + ``action_form``) ----------------------


@pytest.mark.django_db
def test_publish_posts_ignores_duplicate_and_missing_pks(logged_in, post, other_post):
    both = _call_tool(
        logged_in, "run_blog_blogpost_publish_posts", {"pks": [str(post.pk), str(other_post.pk)]}
    )
    assert both["messages"] == [{"level": "success", "message": "Published 2 post(s)."}]

    mixed = _call_tool(
        logged_in,
        "run_blog_blogpost_publish_posts",
        {"pks": [str(post.pk), MISSING_PK, str(post.pk)]},
    )
    assert mixed["messages"] == [{"level": "success", "message": "Published 1 post(s)."}]


@pytest.mark.django_db
def test_bulk_action_without_pks_is_rejected(logged_in, post):
    result = _call_tool(logged_in, "run_blog_blogpost_publish_posts", {"pks": []})
    assert result["errors"] == {
        "pks": [{"message": "Select at least one item.", "code": "required"}]
    }


@pytest.mark.django_db
def test_assign_editor_sets_and_clears_the_editor(logged_in, post, staff_user):
    pks = {"pks": [str(post.pk)]}
    _call_tool(logged_in, "run_blog_blogpost_assign_editor", {**pks, "editor": str(staff_user.pk)})
    post.refresh_from_db()
    assert post.editor == staff_user

    # Like an empty <select> in the admin: no editor means "clear it".
    cleared = _call_tool(logged_in, "run_blog_blogpost_assign_editor", pks)
    assert cleared["messages"] == [{"level": "info", "message": "Updated 1 post(s)."}]
    post.refresh_from_db()
    assert post.editor is None


@pytest.mark.django_db
@pytest.mark.parametrize("editor", [MISSING_PK, "staff"])
def test_assign_editor_rejects_an_unknown_editor(logged_in, post, editor):
    result = _call_tool(
        logged_in, "run_blog_blogpost_assign_editor", {"pks": [str(post.pk)], "editor": editor}
    )
    assert [error["code"] for error in result["errors"]["editor"]] == ["invalid_choice"]


@pytest.mark.django_db
def test_action_form_fields_are_shared_by_every_bulk_action(logged_in):
    # Django's action_form is one form for all bulk actions, so every bulk
    # tool takes `editor`; only assign_editor actually reads it.
    tools = _run_tools(logged_in)
    for name in ("publish_posts", "assign_editor", "archive_selected"):
        assert set(tools[f"run_blog_blogpost_{name}"]["inputSchema"]["properties"]) == {
            "pks",
            "editor",
        }


# --- model actions (actions_list) ---------------------------------------------


@pytest.mark.django_db
def test_export_csv_escapes_quotes_commas_and_unicode(logged_in, staff_user):
    post = BlogPost.objects.create(title='QA <b>html</b> & "кавычки", ok', author=staff_user)
    result = _call(logged_in, "run_blog_blogpost_export_all_posts", {})
    assert result["content"][1]["resource"]["text"].splitlines() == [
        "id,title,status",
        f'{post.pk},"QA <b>html</b> & ""кавычки"", ok",draft',
    ]


# --- what is deliberately not exposed -----------------------------------------


@pytest.mark.django_db
def test_delete_selected_and_submit_line_actions_are_not_tools(logged_in):
    tools = _run_tools(logged_in)
    assert "run_blog_blogpost_delete_selected" not in tools
    assert "run_blog_blogpost_notify_author_on_save" not in tools


# --- permissions --------------------------------------------------------------


@pytest.mark.django_db
def test_superuser_only_action_is_not_callable_by_an_editor(
    client, bearer_login, blog_editor, post
):
    bearer_login(client, blog_editor)
    result = _call(client, "run_blog_blogpost_publish_post", {"pk": str(post.pk)})
    assert result["isError"] is True
    assert "Unknown tool" in result["content"][0]["text"]


@pytest.mark.django_db
def test_view_only_staff_gets_exactly_the_unrestricted_actions(
    client, bearer_login, blog_viewer, post
):
    # Mirrors the admin itself: Django's response_action and Unfold's action
    # views only check `permissions=[...]`, so an action without any is
    # runnable by anyone who can view the changelist — over MCP as in the UI.
    bearer_login(client, blog_viewer)
    assert sorted(_run_tools(client)) == [
        "run_blog_blogpost_append_note",
        "run_blog_blogpost_assign_editor",
        "run_blog_blogpost_create_draft",
        "run_blog_blogpost_export_all_posts",
        "run_blog_blogpost_feature_post",
        "run_blog_blogpost_publish_posts",
        "run_blog_blogpost_set_status",
    ]
    _call_tool(client, "run_blog_blogpost_feature_post", {"pk": str(post.pk)})
    post.refresh_from_db()
    assert post.is_featured is True


# --- DANGER-variant confirmation ----------------------------------------------

ARCHIVE = "run_blog_blogpost_archive_selected"


def _archive_call(*posts):
    return {"name": ARCHIVE, "arguments": {"pks": [str(p.pk) for p in posts]}}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "input_responses",
    [
        {"confirm": {"action": "decline"}},
        {"confirm": {"action": "cancel"}},
        {"confirm": {"action": "accept", "content": {"confirmed": False}}},
        {},  # no answer to the "confirm" request at all
    ],
)
def test_danger_action_is_cancelled_unless_accepted(logged_in, post, input_responses):
    call = _archive_call(post)
    first = _modern_rpc(logged_in, "tools/call", call)
    assert first["inputRequests"]["confirm"]["params"]["message"] == (
        "Run “Archive selected posts” on 1 item(s)?"
    )

    result = _answer(logged_in, call, input_responses, first["requestState"])
    assert result["structuredContent"]["errors"] == {
        "__all__": [{"message": "Cancelled by the user.", "code": "cancelled"}]
    }
    post.refresh_from_db()
    assert post.status == "draft"


@pytest.mark.django_db
def test_danger_action_accept_without_confirmed_field_runs(logged_in, post):
    # The form's `confirmed` checkbox defaults to true; an untouched form
    # submits no content.
    call = _archive_call(post)
    first = _modern_rpc(logged_in, "tools/call", call)
    _answer(logged_in, call, {"confirm": {"action": "accept"}}, first["requestState"])
    post.refresh_from_db()
    assert post.status == "archived"


@pytest.mark.django_db
def test_confirmation_cannot_be_moved_to_other_arguments(logged_in, post, other_post):
    first = _modern_rpc(logged_in, "tools/call", _archive_call(post))
    status, body = _modern_raw(
        logged_in,
        {
            **_archive_call(other_post),
            "inputResponses": ACCEPT,
            "requestState": first["requestState"],
        },
    )
    assert status == 400
    assert body["error"]["message"] == "Invalid or expired requestState"
    other_post.refresh_from_db()
    assert other_post.status == "draft"


# F1 (fixed): answers sent without the server-minted requestState used to
# run a destructive tool with no confirmation round at all.
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("tool", "arguments_of"),
    [
        (ARCHIVE, lambda post: {"pks": [str(post.pk)]}),
        ("delete_blog_blogpost", lambda post: {"pk": str(post.pk)}),
    ],
)
def test_confirmation_cannot_be_skipped(logged_in, post, tool, arguments_of):
    status, body = _modern_raw(
        logged_in, {"name": tool, "arguments": arguments_of(post), "inputResponses": ACCEPT}
    )
    assert status == 200
    assert "inputRequests" in body["result"]  # asked again instead of running
    post.refresh_from_db()
    assert post.status == "draft"


# F2 (fixed): one confirmation could be replayed into any number of runs
# within the requestState TTL.
@pytest.mark.django_db
def test_confirmation_is_single_use(logged_in, post):
    call = _archive_call(post)
    first = _modern_rpc(logged_in, "tools/call", call)
    _answer(logged_in, call, ACCEPT, first["requestState"])
    post.refresh_from_db()
    assert post.status == "archived"

    BlogPost.objects.filter(pk=post.pk).update(status="draft")
    replay = _answer(logged_in, call, ACCEPT, first["requestState"])
    assert "inputRequests" in replay
    post.refresh_from_db()
    assert post.status == "draft"


# F3 (fixed): a malformed pk reached the ORM and came back as a raw
# "Field 'id' expected a number" ValueError.
@pytest.mark.django_db
@pytest.mark.parametrize("pks", [["abc"], ["1", "abc", "2.5"]])
def test_bulk_action_rejects_malformed_pks(logged_in, post, pks):
    result = _call_tool(logged_in, "run_blog_blogpost_publish_posts", {"pks": pks})
    invalid = ", ".join(pk for pk in pks if not pk.isdigit())
    assert result == {
        "success": False,
        "messages": [],
        "errors": {"pks": [{"message": f"Invalid primary key(s): {invalid}.", "code": "invalid"}]},
        "returned_page": False,
    }


# --- known bugs, written as the expected behavior ------------------------------


# F4: when none of the selected pks exist, the action still "succeeds" with
# "Published 0 post(s)." — an agent can't tell it acted on nothing.
@pytest.mark.xfail(strict=True, reason="F4: bulk action on only-missing pks reports success")
@pytest.mark.django_db
def test_bulk_action_on_only_missing_pks_fails(logged_in):
    result = _call_tool(
        logged_in, "run_blog_blogpost_publish_posts", {"pks": [MISSING_PK, "99998"]}
    )
    assert result["success"] is False
    assert [error["code"] for error in result["errors"]["pks"]] == ["not_found"]


# F5: a DANGER action asks for confirmation before validating its input, so
# the user confirms "Archive selected posts?" for an empty selection and only
# then gets "Select at least one item.".
@pytest.mark.xfail(strict=True, reason="F5: confirmation is asked before input validation")
@pytest.mark.django_db
def test_danger_action_validates_before_asking_for_confirmation(logged_in):
    result = _modern_rpc(logged_in, "tools/call", {"name": ARCHIVE, "arguments": {"pks": []}})
    assert "inputRequests" not in result
    assert result["structuredContent"]["errors"] == {
        "pks": [{"message": "Select at least one item.", "code": "required"}]
    }
