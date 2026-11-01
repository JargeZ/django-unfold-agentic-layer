"""OAuth scopes narrow what a login reaches, end to end: the consent page
grants them, tools/resources outside them are never registered, and every
handler re-checks its scope on each call (see ``scopes.py``)."""

import hashlib
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from django.test import Client
from django_unfold_agentic_layer import scopes
from django_unfold_agentic_layer.mcp_server.builders.build_admin_mcp_instance import (
    BuildAdminMCPInstance,
)
from django_unfold_agentic_layer.models import OAuthToken
from server.apps.blog.models import BlogPost

from tests.test_mcp_admin_tools import _rpc
from tests.test_oauth import REDIRECT_URI, _path, _start_authorization
from tests.test_security import _call_is_refused, _raw

LIST_URI = "dj-admin://blog/blogpost/"


def _blog_post_tools(client) -> set[str]:
    return {t["name"] for t in _rpc(client, "tools/list")["tools"] if "blog_blogpost" in t["name"]}


@pytest.fixture
def post(staff_user) -> BlogPost:
    return BlogPost.objects.create(title="Post", author=staff_user)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("granted", "expected"),
    [
        ([scopes.READ], set()),
        (
            [scopes.READ, scopes.WRITE],
            {"create_blog_blogpost", "update_blog_blogpost", "run_blog_blogpost_publish_posts"},
        ),
        (
            [scopes.READ, scopes.DESTRUCTIVE],
            {"delete_blog_blogpost", "run_blog_blogpost_archive_selected"},
        ),
    ],
    ids=["read", "read+write", "read+destructive"],
)
def test_tools_outside_the_scopes_are_not_even_listed(
    client, bearer_login, staff_user, granted, expected
):
    bearer_login(client, staff_user, scopes=granted)

    tools = _blog_post_tools(client)

    # Each scope's representative tools are there, and none of the others.
    assert expected <= tools
    if scopes.WRITE not in granted:
        assert not {t for t in tools if t.startswith(("create_", "update_"))}
        assert "run_blog_blogpost_publish_posts" not in tools
    if scopes.DESTRUCTIVE not in granted:
        assert not {t for t in tools if t.startswith("delete_")}
        assert "run_blog_blogpost_archive_selected" not in tools
    # mcp:read is always there: resources stay readable.
    assert "error" not in _raw(client, "resources/read", {"uri": LIST_URI}).json()


@pytest.mark.django_db
def test_resources_need_the_read_scope(client, bearer_login, staff_user, post):
    bearer_login(client, staff_user, scopes=[scopes.WRITE])

    assert "error" in _raw(client, "resources/read", {"uri": f"{LIST_URI}{post.pk}/"}).json()


@pytest.mark.django_db
def test_every_handler_rechecks_its_scope(client, bearer_login, staff_user, post, monkeypatch):
    """Even a server built with more tools than the login's scopes (a stale
    or wrong build) refuses at call time."""
    build = BuildAdminMCPInstance.execute

    def build_with_every_scope(self, request, *args, **kwargs):
        granted, request.mcp_scopes = request.mcp_scopes, frozenset(scopes.ALL)
        try:
            return build(self, request, *args, **kwargs)
        finally:
            request.mcp_scopes = granted

    monkeypatch.setattr(BuildAdminMCPInstance, "execute", build_with_every_scope)
    bearer_login(client, staff_user, scopes=[scopes.READ])

    assert _call_is_refused(client, "update_blog_blogpost", {"pk": post.pk, "title": "Hacked"})
    assert _call_is_refused(client, "run_blog_blogpost_publish_posts", {"pks": [post.pk]})
    body = _raw(
        client, "tools/call", {"name": "delete_blog_blogpost", "arguments": {"pk": post.pk}}
    )
    assert "not granted the mcp:destructive scope" in body.content.decode()
    post.refresh_from_db()
    assert (post.title, post.status) == ("Post", "draft")


# --- consent ----------------------------------------------------------------


def _approve(browser, consent_url: str, chosen: list[str]) -> list[str]:
    """Approves with ``chosen`` ticked; returns the scopes the code carries."""
    approved = browser.post(consent_url, {"approve": "", "scope": chosen})
    code = parse_qs(urlparse(approved["Location"]).query)["code"][0]
    return _code_scopes(code)


def _code_scopes(code: str) -> list[str]:
    row = OAuthToken.objects.get(token_hash=hashlib.sha256(code.encode()).hexdigest())
    return row.data["scopes"]


@pytest.fixture
def browser() -> Client:
    return Client(HTTP_HOST="localhost")


@pytest.mark.django_db
def test_consent_page_offers_each_requested_scope(browser, staff_user):
    _, _, consent_url, _ = _start_authorization(browser)
    browser.force_login(staff_user)

    page = " ".join(browser.get(consent_url).content.decode().split())

    for scope in scopes.ALL:
        assert f'value="{scope}"' in page
        assert str(scopes.DESCRIPTIONS[scope]) in page
    assert "asks you to confirm each destructive action" in page


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("requested", "chosen", "granted"),
    [
        (None, [scopes.WRITE], [scopes.READ, scopes.WRITE]),
        (None, [], [scopes.READ]),
        (None, scopes.ALL, scopes.ALL),
        # Not asked for, so not grantable, whatever the form says.
        (scopes.READ, [scopes.WRITE, scopes.DESTRUCTIVE], [scopes.READ]),
        (f"{scopes.READ} {scopes.WRITE}", scopes.ALL, [scopes.READ, scopes.WRITE]),
        # Unknown values are ignored.
        (None, ["admin:everything"], [scopes.READ]),
    ],
)
def test_consent_grants_what_was_chosen_within_what_was_requested(
    browser, staff_user, requested, chosen, granted
):
    _, _, consent_url, _ = _start_authorization(browser, scope=requested)
    browser.force_login(staff_user)

    assert _approve(browser, consent_url, chosen) == granted


@pytest.mark.django_db
def test_token_carries_the_granted_scopes(browser, staff_user, post):
    metadata, client_id, consent_url, verifier = _start_authorization(browser)
    browser.force_login(staff_user)
    approved = browser.post(consent_url, {"approve": "", "scope": [scopes.WRITE]})
    code = parse_qs(urlparse(approved["Location"]).query)["code"][0]

    tokens = browser.post(
        _path(metadata["token_endpoint"]),
        urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": client_id,
                "code_verifier": verifier,
            }
        ),
        content_type="application/x-www-form-urlencoded",
    ).json()

    assert tokens["scope"] == f"{scopes.READ} {scopes.WRITE}"
    agent = Client(HTTP_HOST="localhost", HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
    assert "update_blog_blogpost" in _blog_post_tools(agent)
    assert "delete_blog_blogpost" not in _blog_post_tools(agent)


@pytest.mark.django_db
def test_discovery_advertises_the_scopes(browser):
    metadata, *_ = _start_authorization(browser)
    resource = browser.get("/mcp/.well-known/oauth-protected-resource").json()

    assert metadata["scopes_supported"] == resource["scopes_supported"] == scopes.ALL
