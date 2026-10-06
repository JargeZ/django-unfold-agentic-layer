"""Real end-to-end MCP OAuth login, driven the way an MCP client (Claude
Code, Cursor, ...) does it: 401 -> discovery -> dynamic registration ->
browser authorize/consent -> PKCE token exchange -> Bearer calls.

Runs both as plain-http ``localhost`` (the MCP SDK accepts http only for
loopback hosts) and as a real host behind a TLS-terminating proxy, which
must work through Django's standard ``SECURE_PROXY_SSL_HEADER``.
"""

import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from django.test import Client
from django_unfold_agentic_layer.models import OAuthClient

REDIRECT_URI = "http://localhost:33418/callback"


PROXY_HOST = "admin.example.com"


@pytest.fixture
def browser() -> Client:
    return Client(HTTP_HOST="localhost")


@pytest.fixture
def proxied_browser(settings) -> Client:
    """A client reaching Django through a TLS-terminating reverse proxy,
    configured the standard Django way."""
    settings.ALLOWED_HOSTS = [PROXY_HOST]
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    return Client(HTTP_HOST=PROXY_HOST, HTTP_X_FORWARDED_PROTO="https")


@pytest.fixture(params=["localhost", "https-proxy"])
def deployment(request) -> tuple[Client, str]:
    """``(browser, base URL)`` for each way the endpoint is commonly served."""
    if request.param == "localhost":
        return request.getfixturevalue("browser"), "http://localhost"
    return request.getfixturevalue("proxied_browser"), f"https://{PROXY_HOST}"


def _path(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path


def _tools_list(client: Client, token: str | None = None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.post(
        "/mcp",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
        **headers,
    )


def _start_authorization(
    browser: Client, base: str = "http://localhost"
) -> tuple[dict, str, str, str]:
    """Discovery + registration + /authorize, exactly as a client would.
    Returns (AS metadata, client_id, consent URL, PKCE verifier)."""
    unauthorized = _tools_list(browser)
    assert unauthorized.status_code == 401
    prm_url = unauthorized["WWW-Authenticate"].split('resource_metadata="')[1].rstrip('"')
    assert prm_url == f"{base}/mcp/o/.well-known/oauth-protected-resource"

    prm = browser.get(_path(prm_url)).json()
    assert prm["resource"] == f"{base}/mcp"
    (issuer,) = prm["authorization_servers"]
    metadata = browser.get(_path(f"{issuer}/.well-known/openid-configuration")).json()
    assert metadata["issuer"] == issuer == f"{base}/mcp/o"
    for endpoint in ("authorization_endpoint", "token_endpoint", "registration_endpoint"):
        assert metadata[endpoint].startswith(f"{base}/mcp/o/")

    registered = browser.post(
        _path(metadata["registration_endpoint"]),
        data=json.dumps(
            {
                "client_name": "Test Agent",
                "redirect_uris": [REDIRECT_URI],
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code"],
                "response_types": ["code"],
            }
        ),
        content_type="application/json",
    )
    assert registered.status_code == 201, registered.content
    client_id = registered.json()["client_id"]

    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    authorize = browser.get(
        _path(metadata["authorization_endpoint"]),
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "xyz",
            "resource": prm["resource"],
        },
    )
    assert authorize.status_code == 302, authorize.content
    return metadata, client_id, _path(authorize["Location"]), verifier


@pytest.mark.django_db
def test_full_oauth_login_flow(deployment, staff_user, freezer):
    browser, base = deployment
    metadata, client_id, consent_url, verifier = _start_authorization(browser, base)

    # Not logged in yet: the consent page bounces to the admin login.
    assert browser.get(consent_url)["Location"].startswith("/admin/login/")
    browser.force_login(staff_user)
    assert b"Test Agent" in browser.get(consent_url).content

    approved = browser.post(consent_url, {"approve": ""})
    assert approved.status_code == 302
    assert approved["Location"].startswith(REDIRECT_URI)
    query = parse_qs(urlparse(approved["Location"]).query)
    assert query["state"] == ["xyz"]

    exchange = {
        "grant_type": "authorization_code",
        "code": query["code"][0],
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    token_url = _path(metadata["token_endpoint"])
    tokens = browser.post(
        token_url, urlencode(exchange), content_type="application/x-www-form-urlencoded"
    )
    assert tokens.status_code == 200, tokens.content
    body = tokens.json()
    assert body["expires_in"] == 86400
    assert "refresh_token" not in body

    # Codes are single-use.
    replay = browser.post(
        token_url, urlencode(exchange), content_type="application/x-www-form-urlencoded"
    )
    assert replay.json()["error"] == "invalid_grant"

    # The cookie session alone no longer authenticates /mcp/ — only the token does.
    assert _tools_list(browser).status_code == 401
    assert _tools_list(browser, body["access_token"]).status_code == 200

    freezer.tick(86400 + 1)
    assert _tools_list(browser, body["access_token"]).status_code == 401


@pytest.mark.django_db
def test_consent_requires_staff_and_can_be_denied(browser, regular_user, staff_user):
    _, _, consent_url, _ = _start_authorization(browser)

    browser.force_login(regular_user)
    assert browser.get(consent_url)["Location"].startswith("/admin/login/")

    browser.force_login(staff_user)
    denied = browser.post(consent_url, {"deny": ""})
    assert parse_qs(urlparse(denied["Location"]).query) == {
        "error": ["access_denied"],
        "state": ["xyz"],
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/mcp/o/.well-known/oauth-protected-resource",
        "/mcp/o/.well-known/openid-configuration",
        "/mcp/o/register",
        "/mcp/o/authorize",
        "/mcp/o/token",
    ],
)
def test_plain_http_non_loopback_host_explains_the_proxy_setting(settings, path):
    """A TLS proxy Django wasn't told about (no SECURE_PROXY_SSL_HEADER) must
    not advertise unusable http:// URLs or crash with a bare 500 — it must
    say what to configure."""
    settings.ALLOWED_HOSTS = [PROXY_HOST]
    client = Client(HTTP_HOST=PROXY_HOST, HTTP_X_FORWARDED_PROTO="https")

    response = client.post(path) if path.endswith(("register", "token")) else client.get(path)

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "server_error"
    assert "SECURE_PROXY_SSL_HEADER" in body["error_description"]
    assert f"http://{PROXY_HOST}/mcp/o" in body["error_description"]


@pytest.mark.django_db
def test_unauthenticated_mcp_call_behind_proxy_points_at_https_metadata(proxied_browser):
    response = _tools_list(proxied_browser)

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == (
        f'Bearer resource_metadata="https://{PROXY_HOST}/mcp/o/.well-known/oauth-protected-resource"'
    )


@pytest.mark.django_db
def test_authorize_for_a_deleted_client_explains_how_to_reconnect(browser):
    """MCP clients cache their registration: once it's deleted in the admin
    (how a session is revoked) or the database is reset, /authorize opens in
    the person's browser, so it must tell them what to do — not show JSON."""
    metadata, client_id, _, _ = _start_authorization(browser)
    OAuthClient.objects.filter(pk=client_id).delete()

    response = browser.get(
        _path(metadata["authorization_endpoint"]),
        {"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT_URI},
    )

    assert response.status_code == 400
    assert response["Content-Type"].startswith("text/html")
    assert "unfold/layouts/unauthenticated.html" in [t.name for t in response.templates]
    content = response.content.decode()
    assert "Clear authentication" in content
    assert client_id in content


@pytest.mark.django_db
def test_unknown_client_id_is_escaped_on_the_page(browser):
    payload = "<script>alert(1)</script>"

    response = browser.get("/mcp/o/authorize", {"client_id": payload})

    assert response.status_code == 400
    assert payload not in response.content.decode()
    assert "&lt;script&gt;" in response.content.decode()
