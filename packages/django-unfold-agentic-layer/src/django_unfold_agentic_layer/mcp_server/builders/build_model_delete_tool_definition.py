from asgiref.sync import sync_to_async
from django.contrib.admin import ModelAdmin
from fastmcp import Context, FastMCP
from mcp.types import ElicitRequest, ElicitRequestFormParams, InputRequiredResult

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.mcp_server.builders._shared import get_django_request
from django_unfold_agentic_layer.resources.actions.delete_model_instance import DeleteModelInstance
from django_unfold_agentic_layer.resources.actions.get_admin_model_instance import (
    GetAdminModelInstance,
)
from django_unfold_agentic_layer.resources.schemas import AdminModelResource

_CONFIRMATION_SCHEMA = {
    "type": "object",
    "properties": {"confirmed": {"type": "boolean"}},
    "required": ["confirmed"],
}


class BuildModelDeleteToolDefinition(BaseLogicAction):
    """Registers a ``delete_{app_label}_{model_name}`` tool on ``mcp`` (spec §9.1).

    Confirmation goes through the modern-protocol ``InputRequiredResult``
    (SEP-2322), not ``ctx.elicit()``: the latter suspends the tool call
    mid-flight waiting on a server-initiated request the client answers over
    the *same* connection, which stateless mode's single-shot POST has no
    channel for (see bridge.py's session manager). ``InputRequiredResult``
    instead *returns* a description of the needed input and lets the client
    re-invoke the tool with the answer — no long-lived connection required,
    proven end-to-end in this session against ``fastmcp.Client``.

    Unlike a resource template, fastmcp *does* offload a plain sync tool
    function to a worker thread automatically — but via a generic
    ``anyio.to_thread`` pool, a different (and not necessarily consistent)
    thread each call, not the thread-sensitive single-worker behavior
    Django's own ``sync_to_async`` gives resources. Explicitly using
    ``sync_to_async(thread_sensitive=True)`` here too keeps every
    Django-touching call in this server on the same consistent thread the
    request came in on.
    """

    def execute(
        self, mcp: FastMCP, model_admin: ModelAdmin, model_resource: AdminModelResource
    ) -> None:
        if not model_resource.can_delete:
            return

        def run_body(pk: str, ctx: Context) -> str | InputRequiredResult:
            request = get_django_request()
            instance = GetAdminModelInstance().execute(model_admin, request, pk)

            if ctx.input_responses is None:
                return InputRequiredResult(
                    result_type="input_required",
                    input_requests={
                        "confirm": ElicitRequest(
                            method="elicitation/create",
                            params=ElicitRequestFormParams(
                                message=(
                                    f"Delete {model_resource.verbose_name} "
                                    f"{instance!s} (pk={pk})? This cannot be undone."
                                ),
                                requestedSchema=_CONFIRMATION_SCHEMA,
                            ),
                        )
                    },
                    request_state=f"pk={pk}",
                )

            if not ctx.input_responses["confirm"].content.get("confirmed"):
                return "Deletion cancelled."

            DeleteModelInstance().execute(model_admin, request, instance)
            return f"Deleted {model_resource.verbose_name} (pk={pk})."

        async def run(pk: str, ctx: Context) -> str | InputRequiredResult:
            return await sync_to_async(run_body, thread_sensitive=True)(pk, ctx)

        run.__name__ = f"delete_{model_resource.app_label}_{model_resource.model_name}"
        run.__doc__ = (
            f"Delete a {model_resource.verbose_name}. Asks for confirmation before deleting."
        )

        mcp.tool(
            run,
            name=run.__name__,
            description=run.__doc__,
            annotations={"destructiveHint": True},
        )
