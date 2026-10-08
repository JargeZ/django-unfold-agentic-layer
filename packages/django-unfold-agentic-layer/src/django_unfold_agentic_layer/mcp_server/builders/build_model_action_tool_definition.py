import base64
import inspect
import json
from typing import Annotated, Any

from django.contrib.admin import ModelAdmin
from fastmcp import Context, FastMCP
from fastmcp.tools import ToolResult
from mcp.types import (
    BlobResourceContents,
    EmbeddedResource,
    InputRequiredResult,
    TextContent,
    TextResourceContents,
)
from pydantic import Field

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.mcp_server.builders._shared import (
    PK,
    build_editable_field_parameter,
    confirmation_request,
    get_django_request,
    is_confirmed,
    run_in_django,
)
from django_unfold_agentic_layer.resources.actions.run_admin_action import RunAdminAction
from django_unfold_agentic_layer.resources.schemas import (
    ActionResult,
    ActionToolInfo,
)

_PK_PARAMETER = inspect.Parameter(
    "pk",
    kind=inspect.Parameter.KEYWORD_ONLY,
    annotation=Annotated[
        PK, Field(description="Primary key of the instance to run the action on.")
    ],
)
_PKS_PARAMETER = inspect.Parameter(
    "pks",
    kind=inspect.Parameter.KEYWORD_ONLY,
    annotation=Annotated[
        list[PK], Field(description="Primary keys of the instances to run the action on.")
    ],
)
_CTX_PARAMETER = inspect.Parameter("ctx", kind=inspect.Parameter.KEYWORD_ONLY, annotation=Context)


class BuildModelActionToolDefinition(BaseLogicAction):
    """Registers a ``run_{app_label}_{model_name}_{action}`` tool on ``mcp``
    for one admin action (see ``ExtractActionTools``/``RunAdminAction``).

    Parameters: ``pk`` (instance actions) or ``pks`` (bulk actions), then the
    action's form fields — optional at the MCP level for the same reason as
    create/update's (``build_editable_field_parameter``): the form does the
    validation and reports errors in one structured shape. Actions marked
    ``variant=DANGER`` ask for confirmation first, like the delete tool.
    """

    def execute(
        self,
        mcp: FastMCP,
        model_admin: ModelAdmin,
        action: ActionToolInfo,
    ) -> None:
        target = {"instance": [_PK_PARAMETER], "bulk": [_PKS_PARAMETER]}.get(action.scope, [])
        parameters = [
            *target,
            *(build_editable_field_parameter(field) for field in action.fields),
            _CTX_PARAMETER,
        ]

        def run_body(ctx: Context, kwargs: dict[str, Any]) -> ToolResult | InputRequiredResult:
            pk, pks = kwargs.pop("pk", None), kwargs.pop("pks", None)
            request = get_django_request()
            if action.dangerous:
                # Validate first, so the user never confirms a run that can't happen.
                invalid = RunAdminAction().execute(
                    model_admin, request, action, kwargs, pk=pk, pks=pks, dry_run=True
                )
                if invalid is not None:
                    return _tool_result(invalid)
                confirmed = is_confirmed(ctx)
                if confirmed is None:
                    target_text = f" on pk={pk}" if pk else f" on {len(pks)} item(s)" if pks else ""
                    return confirmation_request(
                        f"Run “{action.title}”{target_text}?",
                        title="Confirm action",
                        request_state=action.tool_name,
                    )
                if not confirmed:
                    return _tool_result(
                        ActionResult(
                            success=False,
                            errors={
                                "__all__": [
                                    {"message": "Cancelled by the user.", "code": "cancelled"}
                                ]
                            },
                        )
                    )

            result = RunAdminAction().execute(model_admin, request, action, kwargs, pk=pk, pks=pks)
            return _tool_result(result)

        async def run(*, ctx: Context, **kwargs: Any) -> ToolResult | InputRequiredResult:
            return await run_in_django(action.tool_name, run_body, ctx, kwargs)

        run.__name__ = action.tool_name
        run.__doc__ = action.description
        run.__signature__ = inspect.Signature(parameters)
        run.__annotations__ = {p.name: p.annotation for p in parameters} | {
            "return": ToolResult | InputRequiredResult
        }

        mcp.tool(
            run,
            name=action.tool_name,
            description=action.description,
            annotations={"destructiveHint": True} if action.dangerous else None,
        )


def _tool_result(result: ActionResult) -> ToolResult:
    """The summary as structured content (and JSON text, for clients that
    only read text), plus any returned file as an embedded resource."""
    summary = result.model_dump(
        mode="json", exclude={"file": {"text", "content"}}, exclude_none=True
    )
    content: list = [TextContent(type="text", text=json.dumps(summary, ensure_ascii=False))]
    file = result.file
    if file is not None and (file.text is not None or file.content is not None):
        uri = f"file:///{file.filename or 'action-result'}"
        mime_type = file.content_type.split(";")[0]
        resource = (
            TextResourceContents(uri=uri, mime_type=mime_type, text=file.text)
            if file.text is not None
            else BlobResourceContents(
                uri=uri, mime_type=mime_type, blob=base64.b64encode(file.content).decode()
            )
        )
        content.append(EmbeddedResource(type="resource", resource=resource))
    return ToolResult(content=content, structured_content=summary)
