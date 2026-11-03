from collections.abc import Mapping
from typing import Any

from django import forms
from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import flatten_fieldsets, lookup_field
from django.contrib.auth.forms import ReadOnlyPasswordHashWidget
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist
from django.db.models import FileField, Model
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions._shared import (
    is_secret_widget,
    mask_secret,
    related_list_uri,
)

#: Many-to-many values listed per field; the rest are left to a list query.
M2M_LIMIT = 100

#: Per-field notes on values cut short (``{field: note}``), only when any are.
TRUNCATED_KEY = "_truncated"


class GetModelJsonRepresentation(BaseLogicAction):
    """A JSON-safe dict for one instance, holding exactly the fields its
    admin changeform shows: ``flatten_fieldsets(get_fieldsets())`` — the
    same getter the changeform renders from (spec §7.1), so ``fields``,
    ``exclude`` *and* ``fieldsets`` all hide a field here too
    (``get_fields()`` alone ignores ``fieldsets``).

    A field with a password widget is write-only: it reads as a mask (``None``
    when empty), whatever the widget's ``render_value`` says, for a view-only
    user and in ``readonly_fields`` too. Django's password hash is dropped: it
    can't be written either, so a mask would tell an agent nothing.

    A non-model field (``readonly_fields`` entry: a ModelAdmin method, a
    callable, a model method/property) is resolved with the admin's own
    ``lookup_field``, as the changeform does.

    A file field is ``{"name", "url"}`` (``None`` when empty). The URL comes
    from the storage's own ``url()``, so a storage that signs URLs (S3) still
    signs them; a relative one is made absolute for the current request.

    Relations are rendered as resource URIs, not inlined values (spec §8.3):
    an agent that wants the related object's data can follow the link, and
    this avoids both N+1 queries and unbounded recursion (e.g. a self-FK).
    A many-to-many field lists at most ``M2M_LIMIT`` links; when there are
    more, ``TRUNCATED_KEY`` says so and where to query the rest.
    """

    def execute(
        self, model_admin: ModelAdmin, request: HttpRequest, instance: Model
    ) -> dict[str, Any]:
        opts = instance._meta
        # change=False: with change=True, get_form() excludes every field for a
        # view-only user, so no widget would say that a field is secret.
        form_fields = model_admin.get_form(request, instance, change=False).base_fields
        data: dict[str, Any] = {"pk": instance.pk}
        truncated: dict[str, str] = {}
        for field_name in flatten_fieldsets(model_admin.get_fieldsets(request, instance)):
            widget = self._widget(model_admin, request, opts, form_fields, field_name)
            if isinstance(widget, ReadOnlyPasswordHashWidget):
                continue
            value = self._field_value(model_admin, request, opts, instance, field_name, truncated)
            data[field_name] = mask_secret(value) if is_secret_widget(widget) else value
        if truncated:
            data[TRUNCATED_KEY] = truncated
        return data

    def _widget(
        self,
        model_admin: ModelAdmin,
        request: HttpRequest,
        opts: Any,
        form_fields: Mapping[str, forms.Field],
        field_name: str,
    ) -> forms.Widget | None:
        """The field's widget. A ``readonly_fields`` entry is not in the form,
        so a model column gets the widget its admin configures for that column
        (``formfield_overrides``)."""
        form_field = form_fields.get(field_name)
        if form_field is None:
            try:
                db_field = opts.get_field(field_name)
            except FieldDoesNotExist:
                return None
            if not db_field.concrete or db_field.is_relation:
                return None
            form_field = model_admin.formfield_for_dbfield(db_field, request)
        return form_field.widget if form_field is not None else None

    def _field_value(
        self,
        model_admin: ModelAdmin,
        request: HttpRequest,
        opts: Any,
        instance: Model,
        field_name: str,
        truncated: dict[str, str],
    ) -> Any:
        try:
            field = opts.get_field(field_name)
        except FieldDoesNotExist:
            try:
                _field, _attr, value = lookup_field(field_name, instance, model_admin)
            except (AttributeError, ValueError, ObjectDoesNotExist):
                # Same errors the changeform's AdminReadonlyField hides.
                return None
            return value

        if field.many_to_many:
            list_uri = related_list_uri(model_admin, request, field.related_model)
            # One extra row tells "exactly the limit" from "more than that".
            related = list(getattr(instance, field_name).all()[: M2M_LIMIT + 1])
            if len(related) > M2M_LIMIT:
                truncated[field_name] = (
                    f"Only the first {M2M_LIMIT} are listed; there are more."
                    + (f" Query {list_uri} for the rest." if list_uri else "")
                )
            return [_reference(list_uri, obj.pk) for obj in related[:M2M_LIMIT]]
        if field.many_to_one or field.one_to_one:
            related = getattr(instance, field_name)
            if related is None:
                return None
            return _reference(
                related_list_uri(model_admin, request, field.related_model), related.pk
            )

        if isinstance(field, FileField):
            file = getattr(instance, field_name)
            if not file:
                return None
            return {"name": file.name, "url": request.build_absolute_uri(file.url)}

        return field.value_from_object(instance)


def _reference(list_uri: str | None, pk: Any) -> Any:
    """A related object: its resource URI, or its pk when MCP has no
    resource for its model."""
    return f"{list_uri}{pk}/" if list_uri else pk
