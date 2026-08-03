from typing import Any

from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from django_unfold_agentic_layer.mcp_server import bridge


@method_decorator(csrf_exempt, name="dispatch")
class MCPView(View):
    """MCP Streamable HTTP endpoint (stateless, JSON-response mode).

    Delegates POST bodies into ``mcp_server.bridge.dispatch``. GET/DELETE are
    rejected outright: stateless mode has no session to listen on or tear
    down, so the standalone SSE stream GET would otherwise open has nothing
    to serve.
    """

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"error": "authentication required"}, status=401)
        if not (user.is_active and user.is_staff):
            return JsonResponse({"error": "staff permission required"}, status=403)
        return bridge.dispatch(request)

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseNotAllowed:
        return HttpResponseNotAllowed(["POST"])

    def delete(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseNotAllowed:
        return HttpResponseNotAllowed(["POST"])
