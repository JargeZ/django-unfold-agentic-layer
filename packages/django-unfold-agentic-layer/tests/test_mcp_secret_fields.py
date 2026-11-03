"""Write-only fields: any password widget reads as a mask, and a write only
counts when it carries a real value."""

import json

import pytest
from django import forms
from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django_unfold_agentic_layer.resources.actions._shared import SECRET_MASK, is_secret_widget
from server.apps.blog.models import ApiConnection
from unfold.widgets import UnfoldAdminPasswordToggleWidget, UnfoldAdminPasswordWidget

from tests.conftest import grant_mcp_access
from tests.test_confirm_writes import _question
from tests.test_mcp_admin_resources import _read_resource
from tests.test_mcp_admin_tools import _call_tool, _modern_rpc, _rpc

TOKEN = "real-token-value"  # noqa: S105
URI = "dj-admin://blog/apiconnection/"


class CustomPasswordInput(forms.TextInput):
    input_type = "password"


@pytest.fixture
def connection(db) -> ApiConnection:
    return ApiConnection.objects.create(name="Before", access_token=TOKEN)


@pytest.fixture
def connection_viewer(db) -> User:
    user = User.objects.create_user(username="viewer", password="s3cret", is_staff=True)  # noqa: S106
    user.user_permissions.set(Permission.objects.filter(codename="view_apiconnection"))
    return grant_mcp_access(user)


def _read(client, uri: str) -> tuple[object, str]:
    """A resource's parsed JSON and its Markdown."""
    json_content, markdown_content = _read_resource(client, uri)["contents"]
    return json.loads(json_content["text"]), markdown_content["text"]


@pytest.mark.parametrize(
    "widget",
    [
        forms.PasswordInput(),
        forms.PasswordInput(render_value=True),
        UnfoldAdminPasswordWidget(),
        UnfoldAdminPasswordToggleWidget(render_value=True),
        CustomPasswordInput(),
        forms.MultiWidget([forms.TextInput(), forms.PasswordInput()]),
    ],
)
def test_every_password_widget_is_secret(widget):
    assert is_secret_widget(widget)


@pytest.mark.parametrize(
    "widget", [None, forms.TextInput(), forms.MultiWidget([forms.TextInput(), forms.TextInput()])]
)
def test_other_widgets_are_not_secret(widget):
    assert not is_secret_widget(widget)


@pytest.mark.django_db
def test_reads_return_only_the_mask(client, bearer_login, staff_user, connection):
    bearer_login(client, staff_user)

    detail, detail_markdown = _read(client, f"{URI}{connection.pk}/")
    listed, list_markdown = _read(client, URI)

    assert detail["access_token"] == SECRET_MASK
    assert listed[0]["access_token"] == SECRET_MASK
    assert SECRET_MASK in detail_markdown
    for text in (json.dumps(detail), detail_markdown, json.dumps(listed), list_markdown):
        assert TOKEN not in text


@pytest.mark.django_db
def test_an_empty_secret_reads_as_none(client, bearer_login, staff_user):
    connection = ApiConnection.objects.create(name="Empty", access_token="")
    bearer_login(client, staff_user)

    detail, _markdown = _read(client, f"{URI}{connection.pk}/")

    assert detail["access_token"] is None


@pytest.mark.django_db
def test_a_view_only_user_gets_only_the_mask(client, bearer_login, connection_viewer, connection):
    bearer_login(client, connection_viewer)

    detail, markdown = _read(client, f"{URI}{connection.pk}/")

    assert detail["access_token"] == SECRET_MASK
    assert TOKEN not in markdown


@pytest.mark.django_db
def test_a_readonly_secret_gets_only_the_mask(
    client, bearer_login, staff_user, connection, monkeypatch
):
    monkeypatch.setattr(admin.site._registry[ApiConnection], "readonly_fields", ("access_token",))
    bearer_login(client, staff_user)

    detail, _markdown = _read(client, f"{URI}{connection.pk}/")

    assert detail["access_token"] == SECRET_MASK


@pytest.mark.usefixtures("expose_auth_models")
@pytest.mark.django_db
def test_a_view_only_user_does_not_get_the_password_hash(client, bearer_login, staff_user, db):
    viewer = User.objects.create_user(username="viewer", password="s3cret", is_staff=True)  # noqa: S106
    viewer.user_permissions.set(Permission.objects.filter(codename="view_user"))
    bearer_login(client, grant_mcp_access(viewer))

    detail, markdown = _read(client, f"dj-admin://auth/user/{staff_user.pk}/")

    assert "password" not in detail
    assert staff_user.password not in markdown


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"access_token": SECRET_MASK},
        {"access_token": "••"},
        {"access_token": ""},
        {"access_token": "  "},
    ],
)
@pytest.mark.django_db
def test_update_without_a_real_value_keeps_the_secret(
    client, bearer_login, staff_user, connection, arguments
):
    bearer_login(client, staff_user)

    result = _call_tool(
        client, "update_blog_apiconnection", {"pk": connection.pk, "name": "After", **arguments}
    )

    assert result["success"] is True
    connection.refresh_from_db()
    assert connection.name == "After"
    assert connection.access_token == TOKEN


@pytest.mark.parametrize("new_value", ["new-token", "new•token"])
@pytest.mark.django_db
def test_update_with_a_real_value_replaces_the_secret(
    client, bearer_login, staff_user, connection, new_value
):
    bearer_login(client, staff_user)

    result = _call_tool(
        client, "update_blog_apiconnection", {"pk": connection.pk, "access_token": new_value}
    )

    assert result["success"] is True
    connection.refresh_from_db()
    assert connection.access_token == new_value


@pytest.mark.django_db
def test_create_takes_a_real_value_but_not_the_mask(client, bearer_login, staff_user):
    bearer_login(client, staff_user)

    masked = _call_tool(
        client, "create_blog_apiconnection", {"name": "New", "access_token": SECRET_MASK}
    )
    real = _call_tool(client, "create_blog_apiconnection", {"name": "New", "access_token": TOKEN})

    assert masked["errors"]["access_token"][0]["code"] == "required"
    assert real["success"] is True
    assert ApiConnection.objects.get().access_token == TOKEN


@pytest.mark.django_db
def test_action_form_does_not_take_the_mask(client, bearer_login, staff_user, connection):
    bearer_login(client, staff_user)
    tool = "run_blog_apiconnection_rotate_token"

    masked = _call_tool(client, tool, {"pk": connection.pk, "token": SECRET_MASK})
    real = _call_tool(client, tool, {"pk": connection.pk, "token": "new-token"})

    assert masked["errors"]["token"][0]["code"] == "required"
    assert real["success"] is True
    connection.refresh_from_db()
    assert connection.access_token == "new-token"  # noqa: S105


@pytest.mark.django_db
def test_confirmation_does_not_show_the_new_secret(
    client, bearer_login, staff_user, connection, settings
):
    settings.UNFOLD_AGENTIC_LAYER = {"CONFIRM_WRITES": True}
    bearer_login(client, staff_user)

    asked = _modern_rpc(
        client,
        "tools/call",
        {
            "name": "update_blog_apiconnection",
            "arguments": {"pk": connection.pk, "access_token": "new-token"},
        },
    )

    assert "new-token" not in _question(asked)
    assert f"access_token={SECRET_MASK}" in _question(asked)


@pytest.mark.django_db
def test_tool_schema_says_the_field_is_write_only(client, bearer_login, staff_user):
    bearer_login(client, staff_user)

    tools = {tool["name"]: tool for tool in _rpc(client, "tools/list")["tools"]}

    schema = tools["update_blog_apiconnection"]["inputSchema"]["properties"]
    assert "Write-only secret" in schema["access_token"]["description"]
    assert "Write-only secret" not in schema["name"]["description"]
