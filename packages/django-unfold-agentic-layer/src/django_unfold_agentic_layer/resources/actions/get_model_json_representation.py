from typing import Any

from django import forms
from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import flatten_fieldsets
from django.contrib.auth.forms import ReadOnlyPasswordHashWidget
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction


class GetModelJsonRepresentation(BaseLogicAction):
    """A JSON-safe dict for one instance, holding exactly the fields its
    admin changeform shows: ``flatten_fieldsets(get_fieldsets())`` — the
    same getter the changeform renders from (spec §7.1), so ``fields``,
    ``exclude`` *and* ``fieldsets`` all hide a field here too
    (``get_fields()`` alone ignores ``fieldsets``).

    A field the changeform renders through a value-hiding widget (Django's
    masked password hash, a ``PasswordInput``) is dropped as well: the admin
    never shows its raw value, so neither does MCP.

    Relations are rendered as resource URIs, not inlined values (spec §8.3):
    an agent that wants the related object's data can follow the link, and
    this avoids both N+1 queries and unbounded recursion (e.g. a self-FK).
    """

    def execute(
        self, model_admin: ModelAdmin, request: HttpRequest, instance: Model
    ) -> dict[str, Any]:
        opts = instance._meta
        form_fields = model_admin.get_form(request, instance, change=True).base_fields
        data: dict[str, Any] = {"pk": instance.pk}
        for field_name in flatten_fieldsets(model_admin.get_fieldsets(request, instance)):
            form_field = form_fields.get(field_name)
            if form_field is not None and self._hides_value(form_field.widget):
                continue
            data[field_name] = self._field_value(opts, instance, field_name)
        return data

    def _hides_value(self, widget: forms.Widget) -> bool:
        if isinstance(widget, ReadOnlyPasswordHashWidget):
            return True
        return isinstance(widget, forms.PasswordInput) and not widget.render_value

    def _field_value(self, opts: Any, instance: Model, field_name: str) -> Any:
        try:
            field = opts.get_field(field_name)
        except FieldDoesNotExist:
            # A method/@display field (admin-only, not a model field) — best
            # effort: call it if callable, otherwise report it as-is.
            value = getattr(instance, field_name, None)
            return value() if callable(value) else value

        if field.many_to_many:
            related_opts = field.related_model._meta
            return [
                self._resource_uri(related_opts, obj.pk)
                for obj in getattr(instance, field_name).all()
            ]
        if field.many_to_one or field.one_to_one:
            related = getattr(instance, field_name)
            if related is None:
                return None
            return self._resource_uri(field.related_model._meta, related.pk)

        return field.value_from_object(instance)

    def _resource_uri(self, opts: Any, pk: Any) -> str:
        return f"dj-admin://{opts.app_label}/{opts.model_name}/{pk}/"
