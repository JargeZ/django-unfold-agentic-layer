from typing import Any

from django.contrib.admin import ModelAdmin
from django.contrib.admin.views.main import ChangeList
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.schemas import FilterChoiceInfo, FilterFieldInfo


class ExtractListFilterFields(BaseLogicAction):
    """Fields available for filtering a changelist, keyed by their *real* GET
    parameter name (e.g. ``author__id__exact``), not the model field name.

    Must go through ``ChangeList.get_filters()`` rather than reading
    ``ModelAdmin.list_filter``/field types directly: that's the only place
    Django computes each filter's actual ``expected_parameters()``, and they
    don't follow a guessable convention (a plain FK needs
    ``<field>__<target>__exact`` + ``<field>__isnull``; ``DateFieldListFilter``
    needs ``__gte``/``__lt``; a custom ``SimpleListFilter`` uses its own
    ``parameter_name`` outright).

    ⚠️ Django gotcha this inherits: a filter spec that fails ``has_output()``
    is dropped from ``get_filters()`` entirely — its GET parameter then
    silently does nothing if an agent passes it, exactly like an unrecognized
    ``o=`` value. For a plain FK field this means: below 2 rows in the
    *related* table (``RelatedFieldListFilter.field_choices()`` lists that
    table's own ``get_choices()``, not values actually used on this model —
    a table with 1 user total drops the filter even if every row references
    that user). There is no way around this short of reimplementing
    ``ChangeList.get_filters()``; it also means this schema can differ
    depending on what's currently in the database.
    """

    def execute(self, model_admin: ModelAdmin, request: HttpRequest) -> list[FilterFieldInfo]:
        cl = model_admin.get_changelist_instance(request)
        filter_specs, *_ = cl.get_filters(request)

        return [field for spec in filter_specs for field in self._to_filter_fields(cl, spec)]

    def _to_filter_fields(self, cl: ChangeList, spec: Any) -> list[FilterFieldInfo]:
        title = str(spec.title)
        field_format = type(spec).__name__
        choices = self._extract_choices(cl, spec)
        related_resource_uri = self._related_resource_uri(spec)

        return [
            FilterFieldInfo(
                key=param,
                title=title,
                format=field_format,
                choices=choices,
                related_resource_uri=related_resource_uri,
            )
            for param in spec.expected_parameters()
        ]

    def _extract_choices(self, cl: ChangeList, spec: Any) -> list[FilterChoiceInfo] | None:
        # django-unfold's own dropdown-style filters (RelatedDropdownFilter,
        # AutocompleteSelectFilter, ChoicesDropdownFilter, ...) override
        # choices() to yield a single {"form": <Form instance>} for their own
        # template widget, not Django's per-value {"display", "query_string",
        # "selected"} contract — anything that doesn't match that shape has no
        # usable choices to surface, rather than being a bug to raise on.
        try:
            raw_choices = [
                choice
                for choice in spec.choices(cl)
                if "display" in choice and "query_string" in choice
            ]
        except NotImplementedError:
            return None
        if not raw_choices:
            return None
        return [
            FilterChoiceInfo(display=str(choice["display"]), query_string=choice["query_string"])
            for choice in raw_choices
        ]

    def _related_resource_uri(self, spec: Any) -> str | None:
        related_model = getattr(getattr(spec, "field", None), "related_model", None)
        if related_model is None:
            return None
        opts = related_model._meta
        return f"dj-admin://{opts.app_label}/{opts.model_name}/"
