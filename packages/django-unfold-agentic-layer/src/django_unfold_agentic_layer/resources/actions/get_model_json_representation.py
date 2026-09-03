from typing import Any

from django.contrib.admin import ModelAdmin
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction


class GetModelJsonRepresentation(BaseLogicAction):
    """A JSON-safe dict for one instance, source-of-truth-ordered by
    ``ModelAdmin.get_fields()`` (the same high-level getter the changeform
    itself calls — see spec §7.1) rather than raw model attributes.

    Relations are rendered as resource URIs, not inlined values (spec §8.3):
    an agent that wants the related object's data can follow the link, and
    this avoids both N+1 queries and unbounded recursion (e.g. a self-FK).
    """

    def execute(
        self, model_admin: ModelAdmin, request: HttpRequest, instance: Model
    ) -> dict[str, Any]:
        opts = instance._meta
        data: dict[str, Any] = {"pk": instance.pk}
        for field_name in model_admin.get_fields(request, instance):
            data[field_name] = self._field_value(opts, instance, field_name)
        return data

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
