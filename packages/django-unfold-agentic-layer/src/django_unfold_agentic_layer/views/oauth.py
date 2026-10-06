"""Django side of the MCP OAuth flow — see ``oauth.py`` for the design."""

import logging
from functools import wraps
from typing import Any
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from mcp.server.auth.routes import build_metadata
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import ProtectedResourceMetadata

from django_unfold_agentic_layer import oauth
from django_unfold_agentic_layer.conf import Settings, get_config
from django_unfold_agentic_layer.mcp_server import bridge
from django_unfold_agentic_layer.models import OAuthClient

logger = logging.getLogger(__name__)


def _cors_json(data: dict[str, Any], status: int = 200) -> JsonResponse:
    # Browser-based clients (e.g. MCP Inspector) fetch discovery documents cross-origin.
    return JsonResponse(data, status=status, headers={"Access-Control-Allow-Origin": "*"})


def _requires_https_issuer(view):
    """Answers with an explanatory OAuth ``server_error`` instead of
    advertising (or crashing on) an issuer the SDK won't accept."""

    @wraps(view)
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        error = oauth.issuer_error(request)
        if error is not None:
            logger.error(error)
            return _cors_json({"error": "server_error", "error_description": error}, status=500)
        return view(request, *args, **kwargs)

    return wrapped


@_requires_https_issuer
def protected_resource_metadata(request: HttpRequest) -> JsonResponse:
    """RFC 9728 — where the 401's ``WWW-Authenticate`` header points clients."""
    metadata = ProtectedResourceMetadata(
        resource=oauth.resource_url(request),
        authorization_servers=[oauth.issuer_url(request)],
    )
    return _cors_json(metadata.model_dump(mode="json", exclude_none=True))


@_requires_https_issuer
def authorization_server_metadata(request: HttpRequest) -> JsonResponse:
    """RFC 8414 metadata, served at the OIDC path-appended location
    (``<issuer>/.well-known/openid-configuration``) — the only discovery URL
    MCP clients try that lives under the issuer rather than the host root."""
    metadata = build_metadata(
        oauth.issuer_url(request),
        None,
        ClientRegistrationOptions(enabled=True),
        RevocationOptions(enabled=True),
    )
    metadata.grant_types_supported = ["authorization_code"]  # no refresh tokens
    data = metadata.model_dump(mode="json", exclude_none=True)
    # Required by the OIDC discovery schema some clients (the TS SDK) validate
    # this location against; we issue no ID tokens, so the key set is empty.
    data.update(
        jwks_uri=request.build_absolute_uri(reverse("django_unfold_agentic_layer:oauth-jwks")),
        subject_types_supported=["public"],
        id_token_signing_alg_values_supported=["RS256"],
    )
    return _cors_json(data)


def jwks(request: HttpRequest) -> JsonResponse:
    return _cors_json({"keys": []})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(_requires_https_issuer, name="dispatch")
class OAuthEndpointView(View):
    """Hands ``/authorize``, ``/token``, ``/register`` and ``/revoke`` to the MCP SDK's handlers."""

    def dispatch(
        self, request: HttpRequest, *args: Any, endpoint: str, **kwargs: Any
    ) -> HttpResponse:
        if endpoint == "authorize":
            client_id = request.GET.get("client_id") or request.POST.get("client_id")
            if client_id and not OAuthClient.objects.filter(pk=client_id).exists():
                return _unknown_client(request, client_id)
        return async_to_sync(bridge.call_asgi)(
            oauth.auth_app(request), request, path=f"/{endpoint}"
        )


def _unknown_client(request: HttpRequest, client_id: str) -> HttpResponse:
    """A person-readable page instead of the SDK's JSON error: /authorize is
    opened in a browser, and MCP clients cache their registration, so once
    it's deleted in the admin (or the database is reset) the person is the
    one who has to clear it in their client."""
    return render(
        request,
        "django_unfold_agentic_layer/unknown_client.html",
        {
            **admin.site.each_context(request),
            "title": _("MCP client not recognized"),
            "client_id": client_id,
        },
        status=400,
    )


@method_decorator(staff_member_required, name="dispatch")
@method_decorator(csrf_protect, name="dispatch")
@method_decorator(xframe_options_deny, name="dispatch")
class ConsentView(View):
    """The staff user approves (or denies) the MCP client the SDK sent here.

    Mandatory even though the user just logged in: registration is open
    (RFC 7591), so without it any page could start a flow and silently get a
    code for an already-logged-in staff user.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        consent = oauth.load_consent_request(request.GET.get("request", ""))
        if consent is None:
            return HttpResponseBadRequest("Authorization request is invalid or expired.")
        client, params = consent
        redirect = urlparse(str(params.redirect_uri))
        now = timezone.now()
        return render(
            request,
            "django_unfold_agentic_layer/consent.html",
            {
                # Unfold's layouts need the admin site's context (theme, colors, site_title).
                **admin.site.each_context(request),
                "title": _("Authorize MCP client"),
                "client_name": client.client_name or client.client_id,
                # What the user can sanity-check: where the code is about to be sent.
                "redirect_host": redirect.netloc or f"{redirect.scheme}://",
                "now": now,
                "expires_at": now + get_config()[Settings.SESSION_TTL],
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        consent = oauth.load_consent_request(request.GET.get("request", ""))
        if consent is None:
            return HttpResponseBadRequest("Authorization request is invalid or expired.")
        client, params = consent
        if "approve" in request.POST:
            location = oauth.approve(request.user, client, params)
        else:
            location = oauth.deny(params)
        # Not HttpResponseRedirect: it rejects custom schemes (cursor://,
        # vscode://). The SDK already matched redirect_uri against the
        # client's registered ones before sending the user here.
        return HttpResponse(status=302, headers={"Location": location})
