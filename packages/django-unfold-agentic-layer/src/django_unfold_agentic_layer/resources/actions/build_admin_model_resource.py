from django.contrib.admin import ModelAdmin

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions.extract_app_level_actions import (
    ExtractAppLevelActions,
)
from django_unfold_agentic_layer.resources.actions.extract_each_model_actions import (
    ExtractEachModelActions,
)
from django_unfold_agentic_layer.resources.actions.extract_list_filter_fields import (
    ExtractListFilterFields,
)
from django_unfold_agentic_layer.resources.actions.extract_search_filter_field import (
    ExtractSearchFilterField,
)
from django_unfold_agentic_layer.resources.schemas import AdminModelResource


class BuildAdminModelResource(BaseLogicAction):
    """A single admin-registered model, described as a resource."""

    def execute(self, model_admin: ModelAdmin) -> AdminModelResource:
        opts = model_admin.model._meta

        filter_fields = ExtractListFilterFields().execute(model_admin)
        search_field = ExtractSearchFilterField().execute(model_admin)
        if search_field is not None:
            filter_fields = [search_field, *filter_fields]

        return AdminModelResource(
            verbose_name=str(opts.verbose_name),
            verbose_name_plural=str(opts.verbose_name_plural),
            each_model_actions=ExtractEachModelActions().execute(model_admin),
            app_level_actions=ExtractAppLevelActions().execute(model_admin),
            filter_fields=filter_fields,
        )
