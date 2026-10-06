from django.contrib.admin import ModelAdmin
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions.extract_form_fields import ExtractFormFields
from django_unfold_agentic_layer.resources.schemas import EditableFieldInfo


class ExtractEditableFields(BaseLogicAction):
    """The fields an agent can set when creating/updating this model —
    sourced from ``ModelAdmin.get_form()`` (spec §7.1), the same form the
    changeform itself renders. ``change`` picks which shape of the form to
    describe (add vs. change can expose different fields). There's no live
    instance at schema-build time, so the change shape gets a blank unsaved
    one: admins that branch on ``obj is None`` (``UserAdmin`` swaps in its
    ``add_form``) must still describe their *change* form for update tools.
    """

    def execute(
        self, model_admin: ModelAdmin, request: HttpRequest, change: bool
    ) -> list[EditableFieldInfo]:
        obj = model_admin.model() if change else None
        form_class = model_admin.get_form(request, obj, change=change)
        return ExtractFormFields().execute(form_class.base_fields)
