from django.contrib.admin import ModelAdmin
from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError
from fastmcp.resources import ResourceResult

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.mcp_server.builders._shared import (
    get_django_request,
    run_in_django,
)
from django_unfold_agentic_layer.resources.actions.build_list_resource_result import (
    BuildListResourceResult,
)
from django_unfold_agentic_layer.resources.actions.get_admin_model_instance import (
    GetAdminModelInstance,
)
from django_unfold_agentic_layer.resources.schemas import AdminModelResource


class BuildModelDetailResourceDefinition(BaseLogicAction):
    """Registers ``dj-admin://{app_label}/{model_name}/{pk}/`` on ``mcp`` (spec §3.1).

    Unlike the list resource (§3.2), ``pk`` is the template's only variable,
    so a plain, statically-typed function is enough — no dynamic
    ``inspect.Signature`` construction needed here.
    """

    def execute(
        self, mcp: FastMCP, model_admin: ModelAdmin, model_resource: AdminModelResource
    ) -> None:
        uri_template = f"dj-admin://{model_resource.app_label}/{model_resource.model_name}/{{pk}}/"

        def run(pk: str) -> ResourceResult:
            request = get_django_request()
            instance = GetAdminModelInstance().execute(model_admin, request, pk)
            return BuildListResourceResult().execute(
                model_admin, request, model_resource, [instance], total=1
            )

        # Unlike tools, fastmcp calls a resource template's function directly
        # on the event-loop thread (no automatic thread offload for sync
        # functions) — an ORM call there trips Django's SynchronousOnlyOperation.
        # `async def` + explicit sync_to_async is what actually moves the
        # Django-touching body onto a worker thread.
        async def handler(pk: str) -> ResourceResult:
            return await run_in_django(uri_template, run, pk, error=ResourceError)

        handler.__name__ = f"get_{model_resource.app_label}_{model_resource.model_name}"

        mcp.resource(
            uri=uri_template,
            name=model_resource.verbose_name,
            description=model_resource.description,
            mime_type="application/json",
        )(handler)
