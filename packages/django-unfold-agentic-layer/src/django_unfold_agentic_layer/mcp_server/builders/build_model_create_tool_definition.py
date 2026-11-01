import inspect
from typing import Any

from django.contrib.admin import ModelAdmin
from fastmcp import Context, FastMCP
from mcp.types import InputRequiredResult

from django_unfold_agentic_layer import scopes
from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.mcp_server.builders._shared import (
    CTX_PARAMETER,
    build_editable_field_parameter,
    confirm_write,
    confirm_writes,
    describe_values,
    get_django_request,
    run_in_django,
)
from django_unfold_agentic_layer.resources.actions.create_model_instance import CreateModelInstance
from django_unfold_agentic_layer.resources.schemas import AdminModelResource


class BuildModelCreateToolDefinition(BaseLogicAction):
    """Registers a ``create_{app_label}_{model_name}`` tool on ``mcp`` (spec §9).

    Not registered at all when ``model_resource.can_add`` is false — matches
    the admin itself hiding its "Add" button for a user without that
    permission, rather than exposing a tool that would just error every call.

    ``run`` is ``async def`` + explicit ``sync_to_async(thread_sensitive=True)``
    rather than a plain sync function fastmcp would offload to a worker
    thread itself — see the docstring on ``BuildModelDeleteToolDefinition``
    for why that distinction matters for Django's thread-local connections.
    """

    def execute(
        self, mcp: FastMCP, model_admin: ModelAdmin, model_resource: AdminModelResource
    ) -> None:
        if not model_resource.can_add:
            return

        parameters = [
            *(build_editable_field_parameter(field) for field in model_resource.create_fields),
            CTX_PARAMETER,
        ]

        def run_body(ctx: Context, kwargs: dict[str, Any]) -> dict[str, Any] | InputRequiredResult:
            request = get_django_request(scopes.WRITE)
            if confirm_writes():
                # Validate first, so the user never confirms a save that can't happen.
                _obj, errors = CreateModelInstance().execute(
                    model_admin, request, kwargs, dry_run=True
                )
                if errors:
                    return {"success": False, "errors": errors}
                question = confirm_write(
                    ctx,
                    f"Create {model_resource.verbose_name} ({describe_values(kwargs)})?",
                    request_state=run.__name__,
                )
                if question is not None:
                    return question
            obj, errors = CreateModelInstance().execute(model_admin, request, kwargs)
            if errors:
                return {"success": False, "errors": errors}
            return {
                "success": True,
                "pk": obj.pk,
                "resource_uri": f"dj-admin://{model_resource.app_label}/{model_resource.model_name}/{obj.pk}/",
            }

        async def run(*, ctx: Context, **kwargs: Any) -> dict[str, Any] | InputRequiredResult:
            return await run_in_django(run.__name__, run_body, ctx, kwargs)

        run.__name__ = f"create_{model_resource.app_label}_{model_resource.model_name}"
        run.__doc__ = f"Create a new {model_resource.verbose_name}."
        run.__signature__ = inspect.Signature(parameters)
        run.__annotations__ = {p.name: p.annotation for p in parameters} | {
            "return": dict[str, Any] | InputRequiredResult
        }

        mcp.tool(run, name=run.__name__, description=run.__doc__)
