from collections.abc import Mapping

from django import forms

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions._shared import splits_into_subwidgets
from django_unfold_agentic_layer.resources.schemas import EditableFieldInfo


class ExtractFormFields(BaseLogicAction):
    """Describes a Django form's fields as tool parameters — shared by every
    form-backed tool: create/update (the model's admin form), and admin
    actions (an Unfold dialog form or the changelist ``action_form``).

    Skips fields an agent can't meaningfully set: ``disabled`` ones ignore
    submitted data (e.g. Django's read-only password hash), and hidden-widget
    ones are form plumbing rather than user input (e.g. Unfold's
    ``BaseDialogForm._form_submitted`` marker).
    """

    def execute(self, fields: Mapping[str, forms.Field]) -> list[EditableFieldInfo]:
        return [
            self._field_info(name, field)
            for name, field in fields.items()
            if not field.disabled and not field.widget.is_hidden
        ]

    def _field_info(self, name: str, field: forms.Field, title: str = "") -> EditableFieldInfo:
        python_type, choices, related_resource_uri = self._classify(field)
        parts = None
        if python_type == "multi":
            parts = [
                # A subfield has no label: name it by type (date, time, decimal).
                self._field_info(name + suffix, sub, type(sub).__name__.removesuffix("Field"))
                for suffix, sub in zip(field.widget.widgets_names, field.fields)
            ]
        return EditableFieldInfo(
            name=name,
            title=str(field.label or title.lower() or name),
            required=field.required,
            help_text=str(field.help_text or ""),
            python_type=python_type,
            choices=choices,
            related_resource_uri=related_resource_uri,
            parts=parts,
        )

    def _classify(self, field: forms.Field) -> tuple[str, list[tuple[str, str]] | None, str | None]:
        # ModelMultipleChoiceField/ModelChoiceField subclass ChoiceField, so
        # they must be checked before the generic ChoiceField case below.
        if isinstance(field, forms.ModelMultipleChoiceField):
            return "multi_related", None, self._related_resource_uri(field)
        if isinstance(field, forms.ModelChoiceField):
            return "related", None, self._related_resource_uri(field)
        if isinstance(field, forms.MultiValueField) and splits_into_subwidgets(field.widget):
            return "multi", None, None
        if isinstance(field, forms.FileField):
            return "file", None, None
        if isinstance(field, forms.BooleanField):
            return "bool", None, None
        if isinstance(field, forms.ChoiceField):
            return "choice", [(str(value), str(label)) for value, label in field.choices], None
        # FloatField/DecimalField subclass IntegerField: check them first.
        if isinstance(field, forms.FloatField | forms.DecimalField):
            return "float", None, None
        if isinstance(field, forms.IntegerField):
            return "int", None, None
        return "str", None, None

    def _related_resource_uri(self, field: forms.ModelChoiceField) -> str:
        opts = field.queryset.model._meta
        return f"dj-admin://{opts.app_label}/{opts.model_name}/"
