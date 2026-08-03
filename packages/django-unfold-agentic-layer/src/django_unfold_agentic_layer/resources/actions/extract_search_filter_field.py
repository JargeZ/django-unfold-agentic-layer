from django.contrib.admin import ModelAdmin

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.schemas import FilterFieldInfo


class ExtractSearchFilterField(BaseLogicAction):
    """The free-text search box, if ``ModelAdmin.search_fields`` is configured."""

    def execute(self, model_admin: ModelAdmin) -> FilterFieldInfo | None:
        if not model_admin.search_fields:
            return None

        fields = ", ".join(model_admin.search_fields)
        return FilterFieldInfo(
            key="q",
            title="Search",
            format=f"free-text search across: {fields}",
        )
