from django.contrib.admin import ModelAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import Model
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction


class DeleteModelInstance(BaseLogicAction):
    """Deletes one instance through ``ModelAdmin.delete_model()`` — the same
    hook the browser's delete confirmation page calls, so any admin-level
    override (e.g. a soft-delete) still runs.
    """

    def execute(self, model_admin: ModelAdmin, request: HttpRequest, instance: Model) -> None:
        if not model_admin.has_delete_permission(request, instance):
            raise PermissionDenied("You do not have permission to delete this object.")
        model_admin.delete_model(request, instance)
