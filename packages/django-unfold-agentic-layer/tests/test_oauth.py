"""Real end-to-end MCP OAuth login, driven the way an MCP client (Claude
Code, Cursor, ...) does it: 401 -> discovery -> dynamic registration ->
browser authorize/consent -> PKCE token exchange -> Bearer calls.

Runs as ``localhost``: the MCP SDK only accepts a plain-http issuer for
loopback hosts (anything else must be https).
"""

import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from django.test import Client

REDIRECT_URI = "http://localhost:33418/callback"


@pytest.fixture
def browser() -> Client:
    return Client(HTTP_HOST="localhost")


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


def _start_authorization(browser: Client) -> tuple[dict, str, str, str]:
    """Discovery + registration + /authorize, exactly as a client would.
    Returns (AS metadata, client_id, consent URL, PKCE verifier)."""
    unauthorized = _tools_list(browser)
    assert unauthorized.status_code == 401
    prm_url = unauthorized["WWW-Authenticate"].split('resource_metadata="')[1].rstrip('"')
    assert prm_url == "http://localhost/mcp/o/.well-known/oauth-protected-resource"

    prm = browser.get(_path(prm_url)).json()
    assert prm["resource"] == "http://localhost/mcp"
    (issuer,) = prm["authorization_servers"]
    metadata = browser.get(_path(f"{issuer}/.well-known/openid-configuration")).json()
    assert metadata["issuer"] == issuer == "http://localhost/mcp/o"

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
def test_full_oauth_login_flow(browser, staff_user, freezer):
    metadata, client_id, consent_url, verifier = _start_authorization(browser)

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
