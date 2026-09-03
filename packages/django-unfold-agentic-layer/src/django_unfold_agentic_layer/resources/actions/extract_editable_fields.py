from django import forms
from django.contrib.admin import ModelAdmin
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.schemas import EditableFieldInfo


class ExtractEditableFields(BaseLogicAction):
    """The fields an agent can set when creating/updating this model —
    sourced from ``ModelAdmin.get_form()`` (spec §7.1), the same form the
    changeform itself renders. ``change`` picks which shape of the form to
    describe (add vs. change can expose different fields); there's no live
    instance yet at schema-build time, so ``obj`` is always ``None`` — Django's
    own ``get_form()`` already tolerates that (``has_change_permission(request,
    None)`` etc. fall back to their non-object form).
    """

    def execute(
        self, model_admin: ModelAdmin, request: HttpRequest, change: bool
    ) -> list[EditableFieldInfo]:
        form_class = model_admin.get_form(request, None, change=change)
        return [self._field_info(name, field) for name, field in form_class.base_fields.items()]

    def _field_info(self, name: str, field: forms.Field) -> EditableFieldInfo:
        python_type, choices, related_resource_uri = self._classify(field)
        return EditableFieldInfo(
            name=name,
            title=str(field.label or name),
            required=field.required,
            help_text=str(field.help_text or ""),
            python_type=python_type,
            choices=choices,
            related_resource_uri=related_resource_uri,
        )

    def _classify(self, field: forms.Field) -> tuple[str, list[tuple[str, str]] | None, str | None]:
        # ModelMultipleChoiceField/ModelChoiceField subclass ChoiceField, so
        # they must be checked before the generic ChoiceField case below.
        if isinstance(field, forms.ModelMultipleChoiceField):
            return "multi_related", None, self._related_resource_uri(field)
        if isinstance(field, forms.ModelChoiceField):
            return "related", None, self._related_resource_uri(field)
        if isinstance(field, forms.BooleanField):
            return "bool", None, None
        if isinstance(field, forms.ChoiceField):
            return "choice", [(str(value), str(label)) for value, label in field.choices], None
        if isinstance(field, forms.IntegerField):
            return "int", None, None
        if isinstance(field, forms.FloatField | forms.DecimalField):
            return "float", None, None
        return "str", None, None

    def _related_resource_uri(self, field: forms.ModelChoiceField) -> str:
        opts = field.queryset.model._meta
        return f"dj-admin://{opts.app_label}/{opts.model_name}/"
