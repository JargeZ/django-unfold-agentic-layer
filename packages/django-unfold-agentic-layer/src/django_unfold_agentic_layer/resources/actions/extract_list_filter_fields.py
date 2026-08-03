from django.contrib.admin import ModelAdmin
from django.core.exceptions import FieldDoesNotExist

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.schemas import FilterFieldInfo

#: One ``list_filter`` entry: a field name, a (field name, filter class) pair,
#: or a standalone filter class (e.g. a ``SimpleListFilter`` subclass).
ListFilterEntry = str | type | tuple[str, type]


class ExtractListFilterFields(BaseLogicAction):
    """Fields (and custom filter classes) configured on ``ModelAdmin.list_filter``."""

    def execute(self, model_admin: ModelAdmin) -> list[FilterFieldInfo]:
        return [self._to_filter_field(model_admin, entry) for entry in model_admin.list_filter]

    def _to_filter_field(self, model_admin: ModelAdmin, entry: ListFilterEntry) -> FilterFieldInfo:
        if isinstance(entry, str):
            return self._from_field_name(model_admin, entry, filter_class=None)
        if isinstance(entry, type):
            return self._from_filter_class(entry)

        field_name, filter_class = entry
        return self._from_field_name(model_admin, field_name, filter_class=filter_class)

    def _from_field_name(
        self, model_admin: ModelAdmin, field_name: str, filter_class: type | None
    ) -> FilterFieldInfo:
        try:
            field = model_admin.model._meta.get_field(field_name)
            title = str(field.verbose_name)
            field_format = type(field).__name__
        except FieldDoesNotExist:
            title = field_name
            field_format = "unknown"

        if filter_class is not None:
            field_format = f"{field_format} (custom filter: {filter_class.__name__})"

        return FilterFieldInfo(key=field_name, title=title, format=field_format)

    def _from_filter_class(self, filter_class: type) -> FilterFieldInfo:
        key = getattr(filter_class, "parameter_name", None) or filter_class.__name__
        title = getattr(filter_class, "title", None) or filter_class.__name__
        return FilterFieldInfo(
            key=key,
            title=str(title),
            format=f"custom filter: {filter_class.__name__}",
        )
