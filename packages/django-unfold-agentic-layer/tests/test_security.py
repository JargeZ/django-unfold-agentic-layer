"""Security regression suite, end to end through /mcp and /mcp/o.

Each test pins down one way an agent could see or do more than its user can
in the admin right now — not just at first login. Grouped by attack surface:

- permission changes while the process (and its per-user server cache) lives;
- handler-level checks that must hold even when the cached server is stale;
- bearer token lifecycle (revocation, expiry, audience, token kind);
- the OAuth consent step;
- confirmation of destructive tools.
"""

import hashlib
import json
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.test import Client
from django.utils import timezone
from django_unfold_agentic_layer.models import OAuthClient, OAuthToken
from server.apps.blog.admin import BlogPostAdmin
from server.apps.blog.models import BlogPost

from tests.test_mcp_admin_actions_edge_cases import ACCEPT, _modern_raw
from tests.test_mcp_admin_tools import _modern_rpc, _rpc
from tests.test_oauth import REDIRECT_URI, _path, _start_authorization

LIST_URI = "dj-admin://blog/blogpost/"


def _raw(client, method, params):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return client.post(
        "/mcp/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )


def _blog_templates(client) -> set[str]:
    templates = _rpc(client, "resources/templates/list")["resourceTemplates"]
    return {t["uriTemplate"] for t in templates if t["uriTemplate"].startswith(LIST_URI)}


def _blog_tools(client) -> set[str]:
    return {t["name"] for t in _rpc(client, "tools/list")["tools"] if "blog_blogpost" in t["name"]}


def _read_is_refused(client, uri) -> bool:
    body = _raw(client, "resources/read", {"uri": uri}).json()
    return "error" in body


def _call_is_refused(client, name, arguments) -> bool:
    body = _raw(client, "tools/call", {"name": name, "arguments": arguments}).json()
    # Either the tool no longer exists (JSON-RPC error) or it ran and refused.
    return "error" in body or body["result"].get("isError") is True


def _assert_no_blog_access(client, post: BlogPost) -> None:
    """Every read and write path to BlogPost is closed, and nothing changed."""
    assert _read_is_refused(client, LIST_URI)
    assert _read_is_refused(client, f"{LIST_URI}{post.pk}/")
    assert _call_is_refused(client, "update_blog_blogpost", {"pk": str(post.pk), "title": "Hacked"})
    assert _call_is_refused(client, "create_blog_blogpost", {"title": "Injected"})
    assert _call_is_refused(client, "run_blog_blogpost_export_all_posts", {})
    assert _call_is_refused(client, "run_blog_blogpost_feature_post", {"pk": str(post.pk)})
    assert _call_is_refused(client, "run_blog_blogpost_publish_posts", {"pks": [str(post.pk)]})
    post.refresh_from_db()
    assert (post.title, post.status, post.is_featured) == ("Post", "draft", False)
    assert not BlogPost.objects.filter(title="Injected").exists()


@pytest.fixture
def post(staff_user) -> BlogPost:
    return BlogPost.objects.create(title="Post", body="Body", author=staff_user)


@pytest.fixture
def blog_group_member(db) -> User:
    """Staff whose blog permissions come only from a group."""
    group = Group.objects.create(name="blog")
    group.permissions.set(Permission.objects.filter(content_type__app_label="blog"))
    user = User.objects.create_user(username="grouped", is_staff=True)
    user.groups.add(group)
    return user


def _remove_direct_permissions(user: User) -> None:
    user.user_permissions.clear()


def _leave_groups(user: User) -> None:
    user.groups.clear()


def _demote_superuser(user: User) -> None:
    user.is_superuser = False
    user.save()


# --- permission changes while the server cache is warm -----------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("user_fixture", "revoke"),
    [
        ("blog_editor", _remove_direct_permissions),
        ("blog_group_member", _leave_groups),
        ("staff_user", _demote_superuser),
    ],
    ids=["direct-permissions", "group", "superuser"],
)
def test_revoked_access_takes_effect_on_the_next_request(
    request, client, bearer_login, post, user_fixture, revoke
):
    user = request.getfixturevalue(user_fixture)
    bearer_login(client, user)
    assert _blog_templates(client)  # warms the per-user server cache
    assert not _read_is_refused(client, LIST_URI)

    revoke(User.objects.get(pk=user.pk))

    assert _blog_templates(client) == set()
    assert _blog_tools(client) == set()
    _assert_no_blog_access(client, post)


@pytest.mark.django_db
def test_granted_access_takes_effect_on_the_next_request(
    client, bearer_login, staff_user_without_permissions, post
):
    bearer_login(client, staff_user_without_permissions)
    assert _blog_templates(client) == set()

    staff_user_without_permissions.user_permissions.add(
        Permission.objects.get(codename="view_blogpost")
    )

    assert _blog_templates(client)
    assert not _read_is_refused(client, f"{LIST_URI}{post.pk}/")


@pytest.mark.django_db
def test_narrowed_access_drops_only_what_was_revoked(client, bearer_login, blog_editor, post):
    bearer_login(client, blog_editor)
    assert "update_blog_blogpost" in _blog_tools(client)

    blog_editor.user_permissions.remove(Permission.objects.get(codename="change_blogpost"))

    assert "update_blog_blogpost" not in _blog_tools(client)
    assert _call_is_refused(client, "update_blog_blogpost", {"pk": str(post.pk), "title": "x"})
    assert not _read_is_refused(client, f"{LIST_URI}{post.pk}/")  # view is still granted


# --- handlers re-check against the live request ------------------------------


@pytest.mark.django_db
def test_handlers_refuse_when_the_admin_denies_after_the_server_was_built(
    client, bearer_login, staff_user, post, monkeypatch
):
    """A ModelAdmin may override ``has_*_permission`` with rules no permission
    set captures (ownership, time, feature flags), so the cached server can be
    stale without its cache key changing: every handler must ask again."""
    bearer_login(client, staff_user)
    assert _blog_tools(client)  # warm cache, tools registered

    for name in ("view", "change", "add", "delete"):
        monkeypatch.setattr(
            BlogPostAdmin, f"has_{name}_permission", lambda self, request, obj=None: False
        )

    assert _blog_tools(client)  # same cache entry — still registered...
    _assert_no_blog_access(client, post)  # ...but every call is refused


# --- bearer tokens ------------------------------------------------------------


def _issue(user: User, *, kind=OAuthToken.Kind.ACCESS, resource=None, ttl=timedelta(days=1)):
    oauth_client, _ = OAuthClient.objects.get_or_create(client_id="sec", defaults={"info": {}})
    token = secrets.token_urlsafe(32)
    data = {"client_id": "sec", "scopes": []}
    if resource is not None:
        data["resource"] = resource
    OAuthToken.objects.create(
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        kind=kind,
        client=oauth_client,
        user=user,
        data=data,
        expires_at=timezone.now() + ttl,
    )
    return token


def _status(authorization: str | None, client: Client | None = None) -> int:
    headers = {"HTTP_AUTHORIZATION": authorization} if authorization is not None else {}
    response = (client or Client()).post(
        "/mcp/",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
        **headers,
    )
    return response.status_code


@pytest.mark.django_db
@pytest.mark.parametrize(
    "authorization",
    [None, "", "Bearer", "Bearer ", "Basic c3RhZmY6czNjcmV0", "Bearer not-a-real-token"],
)
def test_missing_or_malformed_credentials_are_unauthorized(authorization):
    assert _status(authorization) == 401


@pytest.mark.django_db
def test_admin_session_cookie_does_not_authenticate_mcp(staff_user):
    browser = Client()
    browser.force_login(staff_user)
    assert _status(None, browser) == 401


@pytest.mark.django_db
def test_revoked_token_stops_working_immediately(staff_user):
    token = _issue(staff_user)
    assert _status(f"Bearer {token}") == 200

    OAuthToken.objects.all().delete()  # what deleting it in the admin does

    assert _status(f"Bearer {token}") == 401


@pytest.mark.django_db
def test_expired_token_is_unauthorized(staff_user, freezer):
    token = _issue(staff_user, ttl=timedelta(minutes=5))
    freezer.tick(timedelta(minutes=5, seconds=1))
    assert _status(f"Bearer {token}") == 401


@pytest.mark.django_db
def test_authorization_code_is_not_an_access_token(staff_user):
    code = _issue(staff_user, kind=OAuthToken.Kind.CODE)
    assert _status(f"Bearer {code}") == 401


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("resource", "status"),
    [
        ("http://testserver/mcp", 200),
        ("http://testserver/mcp/", 200),
        ("http://other-host/mcp", 401),
        ("https://testserver/mcp", 401),
        ("http://testserver/other-mcp", 401),
    ],
)
def test_token_is_only_accepted_by_the_resource_it_was_issued_for(staff_user, resource, status):
    assert _status(f"Bearer {_issue(staff_user, resource=resource)}") == status


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["is_active", "is_staff"])
def test_live_token_is_cut_off_when_the_user_loses_staff_access(staff_user, field):
    token = _issue(staff_user)
    setattr(staff_user, field, False)
    staff_user.save()
    assert _status(f"Bearer {token}") == 403


# --- OAuth consent ------------------------------------------------------------


@pytest.fixture
def browser() -> Client:
    return Client(HTTP_HOST="localhost")


@pytest.mark.django_db
def test_tampered_consent_request_is_rejected(browser, staff_user):
    _, _, consent_url, _ = _start_authorization(browser)
    browser.force_login(staff_user)
    tampered = consent_url[:-4] + ("AAAA" if not consent_url.endswith("AAAA") else "BBBB")

    assert browser.get(tampered).status_code == 400
    assert browser.post(tampered, {"approve": ""}).status_code == 400
    assert not OAuthToken.objects.filter(kind=OAuthToken.Kind.CODE).exists()


@pytest.mark.django_db
def test_stale_consent_request_is_rejected(browser, staff_user, freezer):
    _, _, consent_url, _ = _start_authorization(browser)
    browser.force_login(staff_user)
    freezer.tick(timedelta(minutes=10, seconds=1))

    assert browser.post(consent_url, {"approve": ""}).status_code == 400


@pytest.mark.django_db
def test_consent_approval_requires_csrf_token(staff_user):
    """Enforced by the view itself: the test app deliberately has no
    CsrfViewMiddleware, like a host project that removed it."""
    browser = Client(HTTP_HOST="localhost", enforce_csrf_checks=True)
    _, _, consent_url, _ = _start_authorization(browser)
    browser.force_login(staff_user)

    assert browser.post(consent_url, {"approve": ""}).status_code == 403
    assert not OAuthToken.objects.filter(kind=OAuthToken.Kind.CODE).exists()

    page = browser.get(consent_url)
    token = page.cookies["csrftoken"].value
    approved = browser.post(consent_url, {"approve": "", "csrfmiddlewaretoken": token})
    assert approved.status_code == 302
    assert approved["Location"].startswith(REDIRECT_URI)


@pytest.mark.django_db
def test_consent_page_cannot_be_framed(browser, staff_user):
    _, _, consent_url, _ = _start_authorization(browser)
    browser.force_login(staff_user)

    assert browser.get(consent_url)["X-Frame-Options"] == "DENY"


@pytest.mark.django_db
def test_authorize_never_redirects_to_an_unregistered_uri(browser):
    metadata, client_id, _, _ = _start_authorization(browser)

    response = browser.get(
        _path(metadata["authorization_endpoint"]),
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "https://attacker.example/steal",
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
        },
    )

    assert response.status_code == 400
    assert "attacker.example" not in response.get("Location", "")


@pytest.mark.django_db
@pytest.mark.parametrize("tamper", ["verifier", "client_id", "redirect_uri"])
def test_code_exchange_requires_the_original_pkce_client_and_redirect(browser, staff_user, tamper):
    metadata, client_id, consent_url, verifier = _start_authorization(browser)
    browser.force_login(staff_user)
    location = browser.post(consent_url, {"approve": ""})["Location"]
    code = location.split("code=")[1].split("&")[0]
    other_client = browser.post(
        _path(metadata["registration_endpoint"]),
        data=json.dumps({"redirect_uris": [REDIRECT_URI], "token_endpoint_auth_method": "none"}),
        content_type="application/json",
    ).json()["client_id"]

    exchange = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    exchange |= {
        "verifier": {"code_verifier": secrets.token_urlsafe(48)},
        "client_id": {"client_id": other_client},
        "redirect_uri": {"redirect_uri": "http://localhost:1/other"},
    }[tamper]
    response = browser.post(
        _path(metadata["token_endpoint"]),
        urlencode(exchange),
        content_type="application/x-www-form-urlencoded",
    )

    assert response.status_code == 400
    assert "access_token" not in response.json()
    assert not OAuthToken.objects.filter(kind=OAuthToken.Kind.ACCESS).exists()


# --- confirmation of destructive tools ---------------------------------------


@pytest.mark.django_db
def test_delete_confirmation_cannot_be_moved_to_another_object(client, bearer_login, staff_user):
    first, second = (BlogPost.objects.create(title=t, author=staff_user) for t in "AB")
    bearer_login(client, staff_user)
    asked = _modern_rpc(
        client, "tools/call", {"name": "delete_blog_blogpost", "arguments": {"pk": str(first.pk)}}
    )

    status, _ = _modern_raw(
        client,
        {
            "name": "delete_blog_blogpost",
            "arguments": {"pk": str(second.pk)},
            "inputResponses": ACCEPT,
            "requestState": asked["requestState"],
        },
    )

    assert status == 400
    assert BlogPost.objects.filter(pk__in=[first.pk, second.pk]).count() == 2


@pytest.mark.django_db
def test_delete_confirmation_is_single_use(client, bearer_login, staff_user):
    post = BlogPost.objects.create(title="A", author=staff_user)
    bearer_login(client, staff_user)
    call = {"name": "delete_blog_blogpost", "arguments": {"pk": str(post.pk)}}
    asked = _modern_rpc(client, "tools/call", call)
    answer = {**call, "inputResponses": ACCEPT, "requestState": asked["requestState"]}
    assert _modern_raw(client, answer)[0] == 200
    assert not BlogPost.objects.filter(pk=post.pk).exists()

    # Same answer replayed against a new object with the same pk.
    BlogPost.objects.create(pk=post.pk, title="A again", author=staff_user)
    status, body = _modern_raw(client, answer)

    assert status != 200 or "inputRequests" in body["result"]
    assert BlogPost.objects.filter(pk=post.pk).exists()
