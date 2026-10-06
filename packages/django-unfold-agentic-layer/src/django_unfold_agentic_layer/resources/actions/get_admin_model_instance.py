from django.contrib.admin import ModelAdmin
from django.db.models import Model
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction


class GetAdminModelInstance(BaseLogicAction):
    """A single instance by pk, honoring the same object-level view
    permission the admin's own changeform would check.

    Raises ``LookupError`` (fastmcp turns any raised exception from a
    resource/tool handler into an MCP error response) rather than returning
    ``None`` — a missing pk and a permission denial are indistinguishable to
    an agent either way, matching Django's own ``get_object`` behavior of
    returning ``None`` for both.
    """

    def execute(self, model_admin: ModelAdmin, request: HttpRequest, pk: str) -> Model:
        instance = model_admin.get_object(request, pk)
        if instance is None or not model_admin.has_view_permission(request, instance):
            opts = model_admin.model._meta
            raise LookupError(f"No {opts.verbose_name} found with pk={pk!r}")
        return instance
