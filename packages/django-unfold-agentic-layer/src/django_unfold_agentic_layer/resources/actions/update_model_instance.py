from typing import Any

from django.contrib.admin import ModelAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import Model
from django.forms.models import model_to_dict
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions.create_model_instance import (
    FormErrors,
    split_uploads,
)


class UpdateModelInstance(BaseLogicAction):
    """Updates one instance through the model's own admin change-form.

    A Django ``ModelForm`` validates as a whole, so a partial update (an
    agent providing only the field(s) it wants to change) starts from the
    instance's *current* values (``model_to_dict``, which already reports FK/
    M2M fields as raw pks — exactly what the form's fields expect) and
    overlays whatever the agent actually provided, before validating the
    full form. Saving goes through ``ModelAdmin.save_model()``, same as
    ``CreateModelInstance``, so admin-level save overrides still run.
    """

    def execute(
        self, model_admin: ModelAdmin, request: HttpRequest, instance: Model, data: dict[str, Any]
    ) -> tuple[Model | None, FormErrors]:
        if not model_admin.has_change_permission(request, instance):
            raise PermissionDenied("You do not have permission to change this object.")

        form_class = model_admin.get_form(request, instance, change=True)
        current = model_to_dict(instance, fields=list(form_class.base_fields))
        provided, files = split_uploads(data)
        # A file field not in ``files`` keeps its current file (form initial).
        form = form_class(data={**current, **provided}, files=files, instance=instance)
        if not form.is_valid():
            errors = form.errors.get_json_data(escape_html=True)
            # Omitted fields keep their current values — but a required one
            # that is already empty on the record (e.g. a modeltranslation
            # field for a language nobody filled in) has nothing to keep.
            for name, field_errors in errors.items():
                if name not in provided and name not in files:
                    for error in field_errors:
                        if error["code"] == "required":
                            error["message"] = (
                                "This field is required and is empty on the current record, "
                                "so it must be provided."
                            )
            return None, errors

        obj = form.save(commit=False)
        model_admin.save_model(request, obj, form, change=True)
        form.save_m2m()
        return obj, {}
