import inspect
from typing import Annotated, Any

from django.contrib.admin import ModelAdmin
from fastmcp import FastMCP
from pydantic import Field

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.mcp_server.builders._shared import (
    PK,
    build_editable_field_parameter,
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
        ]

        def run_body(pk: str, kwargs: dict[str, Any]) -> dict[str, Any]:
            request = get_django_request()
            instance = GetAdminModelInstance().execute(model_admin, request, pk)
            obj, errors = UpdateModelInstance().execute(model_admin, request, instance, kwargs)
            if errors:
                return {"success": False, "errors": errors}
            return {
                "success": True,
                "pk": obj.pk,
                "resource_uri": f"dj-admin://{model_resource.app_label}/{model_resource.model_name}/{obj.pk}/",
            }

        async def run(*, pk: str, **kwargs: Any) -> dict[str, Any]:
            return await run_in_django(run.__name__, run_body, pk, kwargs)

        run.__name__ = f"update_{model_resource.app_label}_{model_resource.model_name}"
        run.__doc__ = (
            f"Update an existing {model_resource.verbose_name}. "
            "Only send the fields you want to change; omitted fields keep their current "
            "values. A required field that is empty on the record must be sent too."
        )
        run.__signature__ = inspect.Signature(parameters)
        run.__annotations__ = {p.name: p.annotation for p in parameters} | {
            "return": dict[str, Any]
        }

        mcp.tool(run, name=run.__name__, description=run.__doc__)
