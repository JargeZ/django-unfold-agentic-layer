from django.urls import path, re_path

from django_unfold_agentic_layer.views import oauth
from django_unfold_agentic_layer.views.mcp import MCPView

app_name = "django_unfold_agentic_layer"

# Everything, OAuth included, stays under mcp/ so it can't collide with the
# host project's own routes (e.g. a django-oauth-toolkit mounted at /o/).
urlpatterns = [
    # Canonical URL has no trailing slash: clients (e.g. MCP Inspector) POST
    # to exactly what they were given, and POSTs can't be slash-redirected.
    # Advertising "/mcp" as the OAuth resource also covers "/mcp/" under
    # every client's resource-prefix check, not the other way round.
    path("mcp", MCPView.as_view(), name="mcp"),
    path("mcp/", MCPView.as_view()),
    # OAuth lives under the MCP URL itself, which is also the issuer: a client
    # that starts login without first hitting /mcp (so never sees the 401's
    # resource_metadata) derives only <mcp>/.well-known/openid-configuration
    # from the server URL — the one discovery path not at the host's root.
    # "o/" is the previous prefix, kept for clients that cached those URLs;
    # trailing slashes are optional because clients disagree on them.
    re_path(
        r"^mcp/(?:o/)?\.well-known/oauth-protected-resource/?$",
        oauth.protected_resource_metadata,
        name="oauth-protected-resource",
    ),
    re_path(
        r"^mcp/(?:o/)?\.well-known/openid-configuration/?$",
        oauth.authorization_server_metadata,
        name="oauth-authorization-server",
    ),
    re_path(
        r"^mcp/(?:o/)?\.well-known/oauth-authorization-server/?$",
        oauth.authorization_server_metadata,
    ),
    re_path(r"^mcp/(?:o/)?jwks/?$", oauth.jwks, name="oauth-jwks"),
    path("mcp/o/consent", oauth.ConsentView.as_view(), name="oauth-consent"),
    re_path(
        r"^mcp/(?:o/)?(?P<endpoint>authorize|token|register|revoke)/?$",
        oauth.OAuthEndpointView.as_view(),
        name="oauth-endpoint",
    ),
]
