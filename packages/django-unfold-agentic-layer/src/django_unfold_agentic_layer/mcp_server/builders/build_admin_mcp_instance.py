import logging
from functools import lru_cache

from django.contrib.admin import AdminSite
from django.contrib.admin import site as default_admin_site
from django.contrib.auth.base_user import AbstractBaseUser
from django.http import HttpRequest, QueryDict
from django.utils.crypto import salted_hmac
from fastmcp import FastMCP
from mcp.server.request_state import RequestStateSecurity

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.apps import DjangoUnfoldAgenticLayerConfig
from django_unfold_agentic_layer.mcp_server.builders.build_model_action_tool_definition import (
    BuildModelActionToolDefinition,
)
from django_unfold_agentic_layer.mcp_server.builders.build_model_create_tool_definition import (
    BuildModelCreateToolDefinition,
)
from django_unfold_agentic_layer.mcp_server.builders.build_model_delete_tool_definition import (
    BuildModelDeleteToolDefinition,
)
from django_unfold_agentic_layer.mcp_server.builders.build_model_detail_resource_definition import (
    BuildModelDetailResourceDefinition,
)
from django_unfold_agentic_layer.mcp_server.builders.build_model_list_resource_definition import (
    BuildModelListResourceDefinition,
)
from django_unfold_agentic_layer.mcp_server.builders.build_model_update_tool_definition import (
    BuildModelUpdateToolDefinition,
)
from django_unfold_agentic_layer.mcp_server.tools import mcp as docs_mcp
from django_unfold_agentic_layer.resources.actions.build_admin_model_resource import (
    BuildAdminModelResource,
)

logger = logging.getLogger(__name__)


class BuildAdminMCPInstance(BaseLogicAction):
    """The MCP server for one user: the static docs tools (``mcp_server.tools``)
    plus dynamically-generated resources for every admin model that
    ``request.user`` has any permission on (spec §1).

    Returns a *new* ``FastMCP`` rather than mutating a shared singleton —
    the only option compatible with per-user memoization (see
    ``_build_admin_mcp_instance`` below) without racing over shared mutable
    state.
    """

    def execute(self, request: HttpRequest, admin_site: AdminSite = default_admin_site) -> FastMCP:
        return _build_admin_mcp_instance(request.user, admin_site)


@lru_cache
def _build_admin_mcp_instance(user: AbstractBaseUser, admin_site: AdminSite) -> FastMCP:
    """Built once per ``(user, admin_site)`` and cached for the life of the
    process (spec §1.1 — a worker-local cache is accepted as "build once").

    Keyed on the ``user`` model instance itself, not ``user.pk``: Django's own
    ``Model.__eq__``/``__hash__`` already compare/hash by (concrete model,
    pk), so two different ``User`` objects loaded for the same request give
    the same cache entry without this action re-fetching anything itself.

    Deliberately **not** called from ``AppConfig.ready()`` / at import time —
    an import-time side effect reusable Django apps should avoid regardless.

    Tests must bust this between test functions themselves — an autouse
    fixture in the test suite's own conftest.py calls ``cache_clear()``
    directly, rather than depending on a library that patches
    ``functools.lru_cache`` (e.g. pytest-antilru): this module is only ever
    imported lazily, the first time a test calls ``client.post("/mcp/")``
    (Django resolves URLs/views lazily), which is well after such a patch's
    collection-time window has already closed — the cache would silently
    never be registered for busting at all.
    """
    request = _build_schema_request(user)

    # Seal multi-round-trip ``requestState`` (delete confirmation) under a key
    # derived from SECRET_KEY, not fastmcp's per-instance ephemeral default:
    # that one rotates on every runserver reload / differs per worker, so the
    # confirmation round fails with "Invalid or expired requestState".
    request_state_key = salted_hmac("django_unfold_agentic_layer.request_state", "").hexdigest()
    admin_mcp = FastMCP(
        "django_unfold_agentic_layer",
        request_state_security=RequestStateSecurity(keys=[request_state_key]),
    )
    admin_mcp.mount(docs_mcp)

    build_model_resource = BuildAdminModelResource()
    build_detail_resource = BuildModelDetailResourceDefinition()
    build_list_resource = BuildModelListResourceDefinition()
    build_create_tool = BuildModelCreateToolDefinition()
    build_update_tool = BuildModelUpdateToolDefinition()
    build_delete_tool = BuildModelDeleteToolDefinition()
    build_action_tool = BuildModelActionToolDefinition()

    for app in admin_site.get_app_list(request):
        # Our own OAuth clients/tokens: an agent must never be able to read
        # or revoke MCP sessions through MCP itself.
        if app["app_label"] == DjangoUnfoldAgenticLayerConfig.label:
            continue
        for model_dict in app["models"]:
            model_admin = admin_site._registry[model_dict["model"]]
            # One misconfigured ModelAdmin (e.g. add_fieldsets naming fields
            # its form doesn't have) must not take the whole endpoint down —
            # skip that model, keep the rest.
            try:
                model_resource = build_model_resource.execute(model_admin, request)
            except Exception:
                logger.exception("Skipping %s: could not introspect its ModelAdmin", model_admin)
                continue
            build_detail_resource.execute(admin_mcp, model_admin, model_resource)
            build_list_resource.execute(admin_mcp, model_admin, model_resource)
            build_create_tool.execute(admin_mcp, model_admin, model_resource)
            build_update_tool.execute(admin_mcp, model_admin, model_resource)
            build_delete_tool.execute(admin_mcp, model_admin, model_resource)
            for action in model_resource.action_tools:
                build_action_tool.execute(admin_mcp, model_admin, action, model_resource)

    return admin_mcp


def _build_schema_request(user: AbstractBaseUser) -> HttpRequest:
    """A request good enough for *describing* admin models (permission
    checks, filter/action introspection) — not for running one, which is why
    an empty ``GET`` is fine here (see spec §6.1's ``SynthesizeAdminRequest``)."""
    request = HttpRequest()
    request.method = "GET"
    request.user = user
    request.GET = QueryDict()
    return request
