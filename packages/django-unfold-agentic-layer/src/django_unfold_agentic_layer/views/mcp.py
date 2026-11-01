import ipaddress
import json
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
    JsonResponse,
    QueryDict,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from django_unfold_agentic_layer import log, oauth
from django_unfold_agentic_layer.mcp_server import bridge
from django_unfold_agentic_layer.views import login_not_required


# MCP clients send a Bearer token, never a session cookie: a host's
# LoginRequiredMiddleware must not redirect them (see views/__init__.py).
@method_decorator(login_not_required, name="dispatch")
@method_decorator(csrf_exempt, name="dispatch")
class MCPView(View):
    """MCP Streamable HTTP endpoint (stateless, JSON-response mode).

    Authenticates with an OAuth ``Bearer`` access token (see ``oauth.py``) —
    deliberately not the Django session cookie, which MCP clients never send.
    Delegates POST bodies into ``mcp_server.bridge.dispatch``. GET/DELETE are
    rejected outright: stateless mode has no session to listen on or tear
    down, so the standalone SSE stream GET would otherwise open has nothing
    to serve.
    """

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        response = self._post(request)
        if response.status_code >= 400:
            # An MCP client shows an empty body as a bare "Error POSTing to
            # endpoint", so always say why — and leave a trace server-side.
            if not response.content:
                response.content = json.dumps({"error": response.reason_phrase})
                response["Content-Type"] = "application/json"
            # The body may hold admin data, so only DEBUG carries it.
            method = _rpc_method(request)
            log.mcp.warning("MCP %s -> %s", method, response.status_code)
            log.mcp.debug(
                "MCP %s -> %s body: %s",
                method,
                response.status_code,
                response.content[:500].decode(errors="replace"),
            )
        return response

    def _post(self, request: HttpRequest) -> HttpResponse:
        user = oauth.authenticate_bearer(request)
        # Dev-only escape hatch: with UNFOLD_AGENTIC_LAYER_UNAUTHORIZED = True
        # (and DEBUG), a request without a token acts as the first active
        # superuser. Swapping in a real user (rather than skipping the checks)
        # keeps every downstream permission filter running against it.
        if (
            user is None
            and settings.DEBUG
            and getattr(settings, "UNFOLD_AGENTIC_LAYER_UNAUTHORIZED", False)
        ):
            user = (
                get_user_model()
                ._default_manager.filter(is_superuser=True, is_active=True)
                .order_by("pk")
                .first()
            )
            _warn_unauthorized_mode(request, user)

        if user is None:
            # RFC 9728: points MCP clients at the metadata that starts their
            # OAuth login flow.
            metadata_url = request.build_absolute_uri(
                reverse("django_unfold_agentic_layer:oauth-protected-resource")
            )
            return JsonResponse(
                {"error": "authentication required"},
                status=401,
                headers={"WWW-Authenticate": f'Bearer resource_metadata="{metadata_url}"'},
            )
        # Checked on every request, so revoking staff status cuts off live tokens.
        # Deliberately the base AdminSite.has_permission rule, not the site's
        # own: a custom site may require state a bearer request can't carry
        # (django-otp's verified device). That rule already ran at consent
        # (urls.py's admin_view), before this token was issued.
        if not (user.is_active and user.is_staff):
            return JsonResponse({"error": "staff permission required"}, status=403)
        request.user = user
        # /mcp/ takes no query parameters; handlers pass this request to admin
        # hooks (get_queryset, get_form…), which must not see caller-chosen GET.
        request.GET = QueryDict()
        return bridge.dispatch(request)

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseNotAllowed:
        return HttpResponseNotAllowed(["POST"])

    def delete(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseNotAllowed:
        return HttpResponseNotAllowed(["POST"])


def _warn_unauthorized_mode(request: HttpRequest, user: Any) -> None:
    """Warns on every request the dev-only escape hatch serves, and again
    when the caller isn't on this machine — warns, never refuses: it's the
    developer's own setting."""
    log.mcp.warning("UNFOLD_AGENTIC_LAYER_UNAUTHORIZED: tokenless request runs as %s", user)
    remote_addr = request.META.get("REMOTE_ADDR", "")
    try:
        loopback = ipaddress.ip_address(remote_addr).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        log.mcp.warning(
            "UNFOLD_AGENTIC_LAYER_UNAUTHORIZED: tokenless request from non-loopback "
            "address %r — this host is reachable from the network",
            remote_addr,
        )


def _rpc_method(request: HttpRequest) -> str:
    try:
        payload = json.loads(request.body)
    except ValueError:
        return "<invalid JSON>"
    if isinstance(payload, list):
        return ",".join(str(m.get("method")) for m in payload if isinstance(m, dict))
    return str(payload.get("method")) if isinstance(payload, dict) else "<unknown>"
