import json

import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django_unfold_agentic_layer.models import OAuthToken
from server.apps.blog.models import BlogPost
from unfold.admin import ModelAdmin


def test_user_is_registered_with_unfold_admin():
    assert isinstance(admin.site._registry[User], ModelAdmin)


def test_blog_post_is_registered_with_unfold_admin():
    assert isinstance(admin.site._registry[BlogPost], ModelAdmin)


@pytest.mark.django_db
def test_blog_post_round_trips_through_the_database():
    author = User.objects.create_user(username="agent", password="s3cret")  # noqa: S106
    post = BlogPost.objects.create(title="Hello, Unfold", author=author)

    assert BlogPost.objects.get(pk=post.pk).author == author


@pytest.mark.django_db
def test_oauth_admin_lists_sessions_and_delete_revokes_them(client, bearer_login, staff_user):
    mcp = Client()
    bearer_login(mcp, staff_user)
    assert _tools_list(mcp).status_code == 200
    token = OAuthToken.objects.get()

    client.force_login(staff_user)
    clients_page = client.get(reverse("admin:django_unfold_agentic_layer_oauthclient_changelist"))
    assert clients_page.status_code == 200
    assert clients_page.context["cl"].result_list[0].active_tokens == 1
    tokens_page = client.get(reverse("admin:django_unfold_agentic_layer_oauthtoken_changelist"))
    assert list(tokens_page.context["cl"].result_list) == [token]

    client.post(
        reverse("admin:django_unfold_agentic_layer_oauthtoken_delete", args=[token.pk]),
        {"post": "yes"},
    )
    assert _tools_list(mcp).status_code == 401


@pytest.mark.django_db
def test_oauth_models_are_never_exposed_over_mcp(bearer_login, staff_user):
    mcp = Client()
    bearer_login(mcp, staff_user)

    templates = _rpc(mcp, "resources/templates/list").json()["result"]["resourceTemplates"]
    tools = _rpc(mcp, "tools/list").json()["result"]["tools"]

    assert not [t for t in templates if "django_unfold_agentic_layer" in t["uriTemplate"]]
    assert not [t for t in tools if "django_unfold_agentic_layer" in t["name"]]


def _rpc(client, method):
    return client.post(
        "/mcp/",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": {}}),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )


def _tools_list(client):
    return _rpc(client, "tools/list")
