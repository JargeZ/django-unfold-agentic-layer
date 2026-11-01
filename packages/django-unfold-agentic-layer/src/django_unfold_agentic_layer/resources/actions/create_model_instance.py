from typing import Any

from django.contrib.admin import ModelAdmin
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Model
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions._shared import admin_atomic, to_form_data
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
    (spec §9). Saving runs the same ``ModelAdmin`` hooks, in the same order
    and transaction, as the admin's ``_changeform_view``: ``save_form`` →
    ``save_model`` → ``save_related`` → ``log_addition`` (the admin's
    history entry, with its own change message), so any admin-level override (e.g.
    stamping the current user onto a field) still runs, exactly as it would
    from the browser — and a failure in a later hook rolls back the earlier
    ones.

    ``dry_run`` stops after validation (``(None, {})`` when valid), so a
    caller can reject bad input before asking the user to confirm.
    """

    def execute(
        self,
        model_admin: ModelAdmin,
        request: HttpRequest,
        data: dict[str, Any],
        dry_run: bool = False,
    ) -> tuple[Model | None, FormErrors]:
        with admin_atomic(model_admin):
            if not model_admin.has_add_permission(request):
                raise PermissionDenied("You do not have permission to add this object.")

            form_class = model_admin.get_form(request, None, change=False)
            provided, files = split_uploads(data)
            form = form_class(data=to_form_data(form_class.base_fields, provided), files=files)
            if not form.is_valid():
                return None, form.errors.get_json_data(escape_html=True)
            if dry_run:
                return None, {}

            obj = model_admin.save_form(request, form, change=False)
            model_admin.save_model(request, obj, form, change=False)
            model_admin.save_related(request, form, formsets=[], change=False)
            message = model_admin.construct_change_message(request, form, [], add=True)
            model_admin.log_addition(request, obj, message)
            return obj, {}
