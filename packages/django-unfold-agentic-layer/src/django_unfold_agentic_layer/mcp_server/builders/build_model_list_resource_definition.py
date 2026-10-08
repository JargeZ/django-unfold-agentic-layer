import inspect
from typing import Annotated, Any, Literal

from django.contrib.admin import ModelAdmin
from django.core.exceptions import PermissionDenied
from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError
from fastmcp.resources import ResourceResult
from pydantic import Field

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.mcp_server.builders._shared import (
    get_django_request,
    run_in_django,
)
from django_unfold_agentic_layer.resources.actions.apply_mcp_filters_to_request import (
    ApplyMCPFiltersToRequest,
)
from django_unfold_agentic_layer.resources.actions.build_list_resource_result import (
    BuildListResourceResult,
)
from django_unfold_agentic_layer.resources.actions.run_admin_changelist_query import (
    RunAdminChangelistQuery,
)
from django_unfold_agentic_layer.resources.schemas import AdminModelResource, FilterFieldInfo

#: Ceiling on `limit` until UNFOLD_AGENTIC_LAYER grows a setting for it
#: (spec §5.2) — high enough to not get in the way, low enough that an agent
#: can't accidentally request the entire table in one call.
_MAX_LIMIT = 200


class BuildModelListResourceDefinition(BaseLogicAction):
    """Registers ``dj-admin://{app_label}/{model_name}/{?params}`` on ``mcp`` (spec §3.2).

    The parameter set — filter GET params verbatim, plus our own
    ``limit``/``offset``/``order_by`` — varies per model, so the handler's
    ``inspect.Signature`` (and matching ``__annotations__`` — pydantic's
    schema generation resolves types via ``typing.get_type_hints``, which
    reads ``__annotations__`` directly rather than trusting an overridden
    ``__signature__``'s ``Parameter.annotation``) is built at registration
    time instead of written out per model by hand.
    """

    def execute(
        self, mcp: FastMCP, model_admin: ModelAdmin, model_resource: AdminModelResource
    ) -> None:
        parameters = [
            *self._filter_parameters(model_resource.filter_fields),
            self._limit_parameter(model_resource.list_per_page),
            self._offset_parameter(),
            *self._order_by_parameter(model_resource.sortable_fields),
        ]

        def run(kwargs: dict[str, Any]) -> ResourceResult:
            request = get_django_request()
            # The admin's changelist_view check — the cached server only
            # proves the user could view this model when it was built.
            if not model_admin.has_view_permission(request):
                raise PermissionDenied(
                    f"You do not have permission to view {model_resource.verbose_name_plural}."
                )
            limit = kwargs.get("limit", model_resource.list_per_page)
            offset = kwargs.get("offset", 0)

            filtered_request = ApplyMCPFiltersToRequest().execute(request, model_admin, kwargs)
            instances, total = RunAdminChangelistQuery().execute(
                model_admin, filtered_request, limit, offset
            )
            return BuildListResourceResult().execute(
                model_admin, filtered_request, model_resource, instances, total
            )

        # See build_model_detail_resource_definition.py: fastmcp calls a
        # resource template's function directly on the event-loop thread, so
        # the Django-touching body must be explicitly moved to a worker
        # thread via sync_to_async rather than relying on fastmcp to do it.
        async def handler(**kwargs: Any) -> ResourceResult:
            return await run_in_django(base_uri, run, kwargs, error=ResourceError)

        handler.__name__ = f"list_{model_resource.app_label}_{model_resource.model_name}"
        handler.__signature__ = inspect.Signature(parameters)
        handler.__annotations__ = {p.name: p.annotation for p in parameters}

        base_uri = f"dj-admin://{model_resource.app_label}/{model_resource.model_name}/"
        query_param_names = ",".join(p.name for p in parameters)
        uri_template = f"{base_uri}{{?{query_param_names}}}"
        name = f"{model_resource.verbose_name_plural} (list)"
        description = (
            f"First page of {model_resource.verbose_name_plural}. "
            f"Filter, sort and paginate via {uri_template}; one record via {base_uri}{{pk}}/."
        )
        if model_resource.description:
            description = f"{model_resource.description}\n\n{description}"

        mcp.resource(
            uri=uri_template, name=name, description=description, mime_type="application/json"
        )(handler)

        # resources/list returns only concrete resources, and some clients
        # (Claude Code's ListMcpResourcesTool) never call
        # resources/templates/list — without this, nothing looks readable.
        async def first_page() -> ResourceResult:
            return await handler()

        first_page.__name__ = f"{handler.__name__}_first_page"
        mcp.resource(
            uri=base_uri, name=name, description=description, mime_type="application/json"
        )(first_page)

    def _filter_parameters(self, filter_fields: list[FilterFieldInfo]) -> list[inspect.Parameter]:
        return [
            inspect.Parameter(
                field.key,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=None,
                annotation=Annotated[
                    str | None, Field(description=self._filter_description(field))
                ],
            )
            for field in filter_fields
        ]

    def _filter_description(self, field: FilterFieldInfo) -> str:
        description = f"{field.title} ({field.format})"
        if field.choices:
            examples = "; ".join(f"{c.display} -> {c.query_string}" for c in field.choices[:5])
            description = f"{description}. Example values: {examples}"
        return description

    def _limit_parameter(self, list_per_page: int) -> inspect.Parameter:
        return inspect.Parameter(
            "limit",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=list_per_page,
            annotation=Annotated[
                int, Field(ge=1, le=_MAX_LIMIT, description="Max rows to return.")
            ],
        )

    def _offset_parameter(self) -> inspect.Parameter:
        return inspect.Parameter(
            "offset",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=0,
            annotation=Annotated[int, Field(ge=0, description="Rows to skip, for pagination.")],
        )

    def _order_by_parameter(self, sortable_fields: list[str]) -> list[inspect.Parameter]:
        if not sortable_fields:
            return []
        values = [name for field in sortable_fields for name in (field, f"-{field}")]
        return [
            inspect.Parameter(
                "order_by",
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=None,
                annotation=Annotated[
                    Literal[tuple(values)] | None,
                    Field(description="Field to sort by; prefix with - for descending."),
                ],
            )
        ]
