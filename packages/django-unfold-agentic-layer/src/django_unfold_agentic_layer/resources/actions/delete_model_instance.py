from django.contrib.admin import ModelAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import Model
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions._shared import admin_atomic


class DeleteModelInstance(BaseLogicAction):
    """Deletes one instance the way the admin's ``_delete_view`` does, in its
    transaction: ``has_delete_permission`` on the object, then
    ``get_deleted_objects`` — the cascade may not reach a model the user
    cannot delete — then the history entry, then ``delete_model()``, so any admin-level override
    (e.g. a soft-delete) still runs.

    A protected cascade is left to ``delete_model()``'s ``ProtectedError``:
    it names the blocking objects better than the admin's HTML list does.
    """

    def execute(self, model_admin: ModelAdmin, request: HttpRequest, instance: Model) -> None:
        with admin_atomic(model_admin):
            if not model_admin.has_delete_permission(request, instance):
                raise PermissionDenied("You do not have permission to delete this object.")
            _objects, _counts, perms_needed, protected = model_admin.get_deleted_objects(
                [instance], request
            )
            if perms_needed and not protected:
                raise PermissionDenied(
                    f"Deleting it would also delete {', '.join(sorted(perms_needed))}, "
                    "which you do not have permission to delete."
                )
            # The history entry _delete_view writes, before deleting.
            model_admin.log_deletions(request, [instance])
            model_admin.delete_model(request, instance)
