"""Bridges a Django request into FastMCP's Streamable HTTP transport.

Deliberately does not use ``FastMCP.http_app()``/``streamable_http_app()`` — those
assume the parent ASGI application forwards its lifespan (``lifespan=mcp_app.lifespan``),
which Django has no hook for and which the host project should not need to wire up by
hand. Instead, each request builds a fresh, stateless ``StreamableHTTPSessionManager``
and drives it directly with a synthetic ASGI scope reconstructed from ordinary
``HttpRequest`` attributes (not the live ASGI scope/receive channel) so this works
under WSGI as well as ASGI — the pattern is adapted from gts360/django-mcp-server.
"""

from asgiref.sync import async_to_sync
from django.http import HttpRequest, HttpResponse
from fastmcp import FastMCP
from fastmcp.server.http import FastMCPStreamableHTTPSessionManager

from django_unfold_agentic_layer.mcp_server.builders.build_admin_mcp_instance import (
    BuildAdminMCPInstance,
)


async def _dispatch(request: HttpRequest, mcp: FastMCP) -> HttpResponse:
    body = request.body

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": request.method,
        "headers": [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in request.headers.items()
            if key.lower() != "content-length"
        ]
        + [(b"content-length", str(len(body)).encode("latin-1"))],
        "path": request.path,
        "raw_path": request.get_full_path().encode("utf-8"),
        "query_string": request.META["QUERY_STRING"].encode("latin-1"),
        "scheme": "https" if request.is_secure() else "http",
        "client": (request.META.get("REMOTE_ADDR"), 0),
        "server": (request.get_host(), request.get_port()),
        # Namespaced so it can't collide with a real ASGI/ MCP SDK scope key.
        # Resource/tool handlers read it back via
        # mcp_server.builders._shared.get_django_request() —
        # fastmcp.server.dependencies.get_http_request().scope[...] — to get
        # the actor for permission-aware admin lookups (spec §6).
        "django_unfold_agentic_layer.request": request,
    }

    sent: dict = {}
    body_chunks: list[bytes] = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            sent["status"] = message["status"]
            sent["headers"] = message.get("headers", [])
        elif message["type"] == "http.response.body":
            body_chunks.append(message.get("body", b""))

    manager = FastMCPStreamableHTTPSessionManager(
        app=mcp._mcp_server,
        json_response=True,
        stateless=True,
    )
    async with manager.run():
        await manager.handle_request(scope, receive, send)

    headers = {key.decode("latin-1"): value.decode("latin-1") for key, value in sent["headers"]}
    return HttpResponse(b"".join(body_chunks), status=sent["status"], headers=headers)


def dispatch(request: HttpRequest) -> HttpResponse:
    """Synchronous entrypoint — works from a plain Django view under WSGI or ASGI.

    Builds the per-user ``FastMCP`` instance here, in genuinely sync context,
    rather than inside ``_dispatch``: the build touches the ORM (permission
    checks, changelist introspection for the model schema), and ``_dispatch``
    runs inside an event loop (``async_to_sync`` spins one up) where a direct
    ORM call would trip Django's ``SynchronousOnlyOperation`` guard.
    """
    mcp = BuildAdminMCPInstance().execute(request)
    return async_to_sync(_dispatch)(request, mcp)
