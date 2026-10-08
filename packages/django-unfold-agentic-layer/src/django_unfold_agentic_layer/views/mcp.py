from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from django_unfold_agentic_layer import oauth
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
        if not (user.is_active and user.is_staff):
            return JsonResponse({"error": "staff permission required"}, status=403)
        request.user = user
        return bridge.dispatch(request)

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseNotAllowed:
        return HttpResponseNotAllowed(["POST"])

    def delete(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseNotAllowed:
        return HttpResponseNotAllowed(["POST"])
