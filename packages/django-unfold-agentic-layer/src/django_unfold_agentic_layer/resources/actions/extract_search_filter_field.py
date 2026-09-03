from django.contrib.admin import ModelAdmin
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.schemas import FilterFieldInfo


class ExtractSearchFilterField(BaseLogicAction):
    """The free-text search box, if ``ModelAdmin.get_search_fields()`` is non-empty."""

    def execute(self, model_admin: ModelAdmin, request: HttpRequest) -> FilterFieldInfo | None:
        search_fields = model_admin.get_search_fields(request)
        if not search_fields:
            return None

        fields = ", ".join(search_fields)
        return FilterFieldInfo(
            key="q",
            title="Search",
            format=f"free-text search across: {fields}",
        )
