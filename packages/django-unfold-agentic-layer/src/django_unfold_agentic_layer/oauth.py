"""OAuth 2.1 authorization server for the MCP endpoint — storage only.

Every protocol rule (PKCE S256, redirect_uri matching, auth code expiry,
client authentication, RFC 7591 dynamic registration, revocation) is enforced
by the MCP SDK's own handlers (``mcp.server.auth.routes.create_auth_routes``);
this module only backs its ``OAuthAuthorizationServerProvider`` protocol with
Django models and adds the one step the SDK leaves to us: a staff user logging
in and approving the client (``views/oauth.py``'s consent view).

All endpoints live under this app's own ``mcp/o/`` URLs, so nothing here can
collide with a host project's routes, models or settings (e.g. its own
django-oauth-toolkit at ``/o/``). Tokens are opaque random strings stored as
sha256 hashes; no refresh tokens are issued, so ``SESSION_TTL`` is a hard cap
on how long a login lasts.
"""

import hashlib
import secrets
import time
from datetime import timedelta
from functools import lru_cache
from urllib.parse import urlencode

from django.contrib.auth.base_user import AbstractBaseUser
from django.core import signing
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.server.auth.routes import create_auth_routes
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import OAuthClientInformationFull
from mcp.shared.auth import OAuthToken as TokenResponse
from pydantic import AnyHttpUrl
from starlette.applications import Starlette

from django_unfold_agentic_layer.conf import Settings, get_config
from django_unfold_agentic_layer.models import OAuthClient, OAuthToken

_SIGNING_SALT = "django_unfold_agentic_layer.oauth.consent"
#: How long the user has to log in and approve on the consent page.
CONSENT_MAX_AGE = 600
AUTHORIZATION_CODE_TTL = 300


def resource_url(request: HttpRequest) -> str:
    """Absolute URL of the MCP endpoint — the RFC 8707 resource tokens are bound to."""
    return request.build_absolute_uri(reverse("django_unfold_agentic_layer:mcp"))


def issuer_url(request: HttpRequest) -> str:
    """``<mcp>/o`` — has a path, so clients discover the metadata at
    ``<issuer>/.well-known/openid-configuration``, inside our own URLs."""
    return resource_url(request) + "/o"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _live(kind: OAuthToken.Kind, token: str):
    return OAuthToken.objects.filter(
        token_hash=_hash(token), kind=kind, expires_at__gt=timezone.now()
    )


class DjangoOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """Uses Django's async ORM API, which already runs each query on the
    thread-sensitive worker (see CLAUDE.md on ORM access from handlers)."""

    def __init__(self, consent_url: str):
        self.consent_url = consent_url

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        row = await OAuthClient.objects.filter(pk=client_id).afirst()
        return row and OAuthClientInformationFull.model_validate(row.info)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        await OAuthClient.objects.acreate(
            client_id=client_info.client_id, info=client_info.model_dump(mode="json")
        )

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        # Validated params travel signed to the consent page; nothing is
        # stored until a staff user actually approves.
        payload = {"client_id": client.client_id, "params": params.model_dump(mode="json")}
        signed = signing.dumps(payload, salt=_SIGNING_SALT)
        return f"{self.consent_url}?{urlencode({'request': signed})}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        row = (
            await _live(OAuthToken.Kind.CODE, authorization_code)
            .filter(client_id=client.client_id)
            .afirst()
        )
        return row and AuthorizationCode(code=authorization_code, **row.data)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> TokenResponse:
        deleted, _ = await OAuthToken.objects.filter(
            token_hash=_hash(authorization_code.code), kind=OAuthToken.Kind.CODE
        ).adelete()
        if not deleted:  # lost a race with a concurrent exchange of the same code
            raise TokenError(
                error="invalid_grant", error_description="authorization code already used"
            )

        ttl = get_config()[Settings.SESSION_TTL]
        expires_at = timezone.now() + ttl
        token = secrets.token_urlsafe(32)
        access = AccessToken(
            token=token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(expires_at.timestamp()),
            resource=authorization_code.resource,
            subject=authorization_code.subject,
        )
        await OAuthToken.objects.filter(expires_at__lt=timezone.now()).adelete()
        await OAuthToken.objects.acreate(
            token_hash=_hash(token),
            kind=OAuthToken.Kind.ACCESS,
            client_id=client.client_id,
            user_id=authorization_code.subject,
            data=access.model_dump(mode="json", exclude={"token"}),
            expires_at=expires_at,
        )
        return TokenResponse(
            access_token=token,
            expires_in=int(ttl.total_seconds()),
            scope=" ".join(authorization_code.scopes) or None,
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> None:
        return None  # never issued: SESSION_TTL is a hard session cap

    async def exchange_refresh_token(self, client, refresh_token, scopes) -> TokenResponse:
        raise TokenError(
            error="invalid_grant", error_description="refresh tokens are not supported"
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        row = await _live(OAuthToken.Kind.ACCESS, token).afirst()
        return row and AccessToken(token=token, **row.data)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        await OAuthToken.objects.filter(token_hash=_hash(token.token)).adelete()


@lru_cache(maxsize=8)
def _auth_app(issuer: str, consent_url: str) -> Starlette:
    return Starlette(
        routes=create_auth_routes(
            DjangoOAuthProvider(consent_url),
            AnyHttpUrl(issuer),
            client_registration_options=ClientRegistrationOptions(enabled=True),
            revocation_options=RevocationOptions(enabled=True),
        )
    )


def auth_app(request: HttpRequest) -> Starlette:
    """The SDK's ``/authorize``, ``/token``, ``/register``, ``/revoke`` app for this host."""
    consent_url = request.build_absolute_uri(reverse("django_unfold_agentic_layer:oauth-consent"))
    return _auth_app(issuer_url(request), consent_url)


def load_consent_request(
    signed: str,
) -> tuple[OAuthClientInformationFull, AuthorizationParams] | None:
    """Unsigns what ``DjangoOAuthProvider.authorize`` handed the consent page."""
    try:
        payload = signing.loads(signed, salt=_SIGNING_SALT, max_age=CONSENT_MAX_AGE)
    except signing.BadSignature:
        return None
    client = OAuthClient.objects.filter(pk=payload["client_id"]).first()
    if client is None:
        return None
    return (
        OAuthClientInformationFull.model_validate(client.info),
        AuthorizationParams.model_validate(payload["params"]),
    )


def approve(
    user: AbstractBaseUser, client: OAuthClientInformationFull, params: AuthorizationParams
) -> str:
    """Issue an authorization code for ``user`` and return the client redirect URL."""
    code = secrets.token_urlsafe(32)
    authorization_code = AuthorizationCode(
        code=code,
        scopes=params.scopes or [],
        expires_at=time.time() + AUTHORIZATION_CODE_TTL,
        client_id=client.client_id,
        code_challenge=params.code_challenge,
        redirect_uri=params.redirect_uri,
        redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
        resource=params.resource,
        subject=str(user.pk),
    )
    OAuthToken.objects.create(
        token_hash=_hash(code),
        kind=OAuthToken.Kind.CODE,
        client_id=client.client_id,
        user=user,
        data=authorization_code.model_dump(mode="json", exclude={"code"}),
        expires_at=timezone.now() + timedelta(seconds=AUTHORIZATION_CODE_TTL),
    )
    return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)


def deny(params: AuthorizationParams) -> str:
    return construct_redirect_uri(
        str(params.redirect_uri), error="access_denied", state=params.state
    )


def authenticate_bearer(request: HttpRequest) -> AbstractBaseUser | None:
    """The user behind a live ``Authorization: Bearer`` access token, if any."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    row = _live(OAuthToken.Kind.ACCESS, token).select_related("user").first()
    if row is None:
        return None
    resource = row.data.get("resource")
    if resource is not None and resource.rstrip("/") != resource_url(request).rstrip("/"):
        return None  # issued for a different resource (RFC 8707 audience check)
    return row.user
