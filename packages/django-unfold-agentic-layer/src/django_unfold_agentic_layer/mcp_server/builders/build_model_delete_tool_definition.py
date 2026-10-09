from itertools import islice

from django.contrib.admin import ModelAdmin
from django.db.models import ProtectedError, RestrictedError
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import InputRequiredResult

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.mcp_server.builders._shared import (
    PK,
    confirmation_request,
    get_django_request,
    is_confirmed,
    run_in_django,
)
from django_unfold_agentic_layer.resources.actions.delete_model_instance import DeleteModelInstance
from django_unfold_agentic_layer.resources.actions.get_admin_model_instance import (
    GetAdminModelInstance,
)
from django_unfold_agentic_layer.resources.schemas import AdminModelResource

_MAX_LISTED_BLOCKERS = 10


class BuildModelDeleteToolDefinition(BaseLogicAction):
    """Registers a ``delete_{app_label}_{model_name}`` tool on ``mcp`` (spec §9.1).

    Confirmation goes through ``_shared.confirmation_request`` (SEP-2322
    ``InputRequiredResult`` — see there for why not ``ctx.elicit()``).

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

            confirmed = is_confirmed(ctx)
            if confirmed is None:
                return confirmation_request(
                    f"Delete {model_resource.verbose_name} {instance!s} (pk={pk})? "
                    "This cannot be undone.",
                    title="Confirm deletion",
                    request_state=f"pk={pk}",
                )
            if not confirmed:
                return "Deletion cancelled."

            try:
                DeleteModelInstance().execute(model_admin, request, instance)
            except (ProtectedError, RestrictedError) as e:
                blockers = getattr(e, "protected_objects", None) or e.restricted_objects
                listed = ", ".join(
                    f"{obj._meta.verbose_name} {obj} (pk={obj.pk})"
                    for obj in islice(blockers, _MAX_LISTED_BLOCKERS)
                )
                if len(blockers) > _MAX_LISTED_BLOCKERS:
                    listed = f"{listed} and {len(blockers) - _MAX_LISTED_BLOCKERS} more"
                raise ToolError(
                    f"Cannot delete {model_resource.verbose_name} {instance} (pk={pk}): "
                    f"still referenced by {listed}. Delete or reassign those first."
                ) from None
            return f"Deleted {model_resource.verbose_name} (pk={pk})."

        async def run(pk: PK, ctx: Context) -> str | InputRequiredResult:
            return await run_in_django(run.__name__, run_body, pk, ctx)

        run.__name__ = f"delete_{model_resource.app_label}_{model_resource.model_name}"
        run.__doc__ = (
            f"Delete a {model_resource.verbose_name}. Destructive: the server asks the client "
            "for the user's confirmation before deleting."
        )

        mcp.tool(
            run,
            name=run.__name__,
            description=run.__doc__,
            annotations={"destructiveHint": True},
        )
