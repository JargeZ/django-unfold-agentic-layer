from typing import Any

from django.contrib.admin import ModelAdmin
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Model
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.schemas import FileUploadInput

#: Shape of Django's own ``form.errors.get_json_data()`` — reused verbatim
#: rather than inventing a new error format (same spirit as FilterChoiceInfo).
FormErrors = dict[str, list[dict[str, str]]]


def split_uploads(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Tool arguments -> a form's ``(data, files)``: a bound form reads a
    file field only from ``files``, and ignores it in ``data``. Omitted
    (``None``) values are dropped."""
    files = {
        key: SimpleUploadedFile(value.name, value.content)
        for key, value in data.items()
        if isinstance(value, FileUploadInput)
    }
    rest = {key: value for key, value in data.items() if value is not None and key not in files}
    return rest, files


class CreateModelInstance(BaseLogicAction):
    """Creates one instance through the model's own admin add-form —
    ``form.is_valid()`` does all the validation, nothing is duplicated here
    (spec §9). Saving goes through ``ModelAdmin.save_model()`` rather than
    ``form.save()`` directly, so any admin-level override (e.g. stamping the
    current user onto a field) still runs, exactly as it would from the
    browser.
    """

    def execute(
        self, model_admin: ModelAdmin, request: HttpRequest, data: dict[str, Any]
    ) -> tuple[Model | None, FormErrors]:
        if not model_admin.has_add_permission(request):
            raise PermissionDenied("You do not have permission to add this object.")

        form_class = model_admin.get_form(request, None, change=False)
        provided, files = split_uploads(data)
        form = form_class(data=provided, files=files)
        if not form.is_valid():
            return None, form.errors.get_json_data(escape_html=True)

        obj = form.save(commit=False)
        model_admin.save_model(request, obj, form, change=False)
        form.save_m2m()
        return obj, {}
