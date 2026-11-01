import inspect
from typing import Annotated, Any

from django.contrib.admin import ModelAdmin
from fastmcp import Context, FastMCP
from mcp.types import InputRequiredResult
from pydantic import Field

from django_unfold_agentic_layer import scopes
from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.mcp_server.builders._shared import (
    CTX_PARAMETER,
    PK,
    build_editable_field_parameter,
    confirm_write,
    confirm_writes,
    describe_values,
    get_django_request,
    run_in_django,
)
from django_unfold_agentic_layer.resources.actions.get_admin_model_instance import (
    GetAdminModelInstance,
)
from django_unfold_agentic_layer.resources.actions.update_model_instance import UpdateModelInstance
from django_unfold_agentic_layer.resources.schemas import AdminModelResource

_PK_PARAMETER = inspect.Parameter(
    "pk",
    kind=inspect.Parameter.KEYWORD_ONLY,
    annotation=Annotated[PK, Field(description="Primary key of the instance to update.")],
)


class BuildModelUpdateToolDefinition(BaseLogicAction):
    """Registers an ``update_{app_label}_{model_name}`` tool on ``mcp`` (spec §9).

    Every field is optional (see ``build_editable_field_parameter``) — this
    is what makes it a *partial* update: an agent sends only what it wants
    to change, and ``UpdateModelInstance`` fills in the rest from the
    current instance before validating the full form.
    """

    def execute(
        self, mcp: FastMCP, model_admin: ModelAdmin, model_resource: AdminModelResource
    ) -> None:
        if not model_resource.can_change:
            return

        parameters = [
            _PK_PARAMETER,
            *(build_editable_field_parameter(field) for field in model_resource.update_fields),
            CTX_PARAMETER,
        ]

        def run_body(
            ctx: Context, pk: str, kwargs: dict[str, Any]
        ) -> dict[str, Any] | InputRequiredResult:
            request = get_django_request(scopes.WRITE)
            instance = GetAdminModelInstance().execute(model_admin, request, pk)
            if confirm_writes():
                # Named before validating: the form writes the new values onto it.
                current = str(instance)
                # Validate first, so the user never confirms a save that can't happen.
                _obj, errors = UpdateModelInstance().execute(
                    model_admin, request, instance, kwargs, dry_run=True
                )
                if errors:
                    return {"success": False, "errors": errors}
                question = confirm_write(
                    ctx,
                    f"Update {model_resource.verbose_name} {current} (pk={pk}): "
                    f"{describe_values(kwargs)}?",
                    request_state=f"{run.__name__}:{pk}",
                )
                if question is not None:
                    return question
                instance.refresh_from_db()  # undo what the dry run's form wrote onto it
            obj, errors = UpdateModelInstance().execute(model_admin, request, instance, kwargs)
            if errors:
                return {"success": False, "errors": errors}
            return {
                "success": True,
                "pk": obj.pk,
                "resource_uri": f"dj-admin://{model_resource.app_label}/{model_resource.model_name}/{obj.pk}/",
            }

        async def run(
            *, pk: str, ctx: Context, **kwargs: Any
        ) -> dict[str, Any] | InputRequiredResult:
            return await run_in_django(run.__name__, run_body, ctx, pk, kwargs)

        run.__name__ = f"update_{model_resource.app_label}_{model_resource.model_name}"
        run.__doc__ = (
            f"Update an existing {model_resource.verbose_name}. "
            "Only send the fields you want to change; omitted fields keep their current "
            "values. A required field that is empty on the record must be sent too."
        )
        run.__signature__ = inspect.Signature(parameters)
        run.__annotations__ = {p.name: p.annotation for p in parameters} | {
            "return": dict[str, Any] | InputRequiredResult
        }

        mcp.tool(run, name=run.__name__, description=run.__doc__)
