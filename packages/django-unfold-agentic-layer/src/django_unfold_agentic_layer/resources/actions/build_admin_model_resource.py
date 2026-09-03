import inspect

from django.contrib.admin import ModelAdmin
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions.extract_app_level_actions import (
    ExtractAppLevelActions,
)
from django_unfold_agentic_layer.resources.actions.extract_each_model_actions import (
    ExtractEachModelActions,
)
from django_unfold_agentic_layer.resources.actions.extract_editable_fields import (
    ExtractEditableFields,
)
from django_unfold_agentic_layer.resources.actions.extract_list_filter_fields import (
    ExtractListFilterFields,
)
from django_unfold_agentic_layer.resources.actions.extract_search_filter_field import (
    ExtractSearchFilterField,
)
from django_unfold_agentic_layer.resources.actions.extract_sortable_fields import (
    ExtractSortableFields,
)
from django_unfold_agentic_layer.resources.schemas import AdminModelResource


class BuildAdminModelResource(BaseLogicAction):
    """A single admin-registered model, described as a resource.

    Request-aware throughout: every ``Extract*`` call below already applies
    ``request.user``'s permissions (Django's/unfold's own checks), so this
    schema only ever describes what the requesting user could actually do.
    """

    def execute(self, model_admin: ModelAdmin, request: HttpRequest) -> AdminModelResource:
        opts = model_admin.model._meta

        filter_fields = ExtractListFilterFields().execute(model_admin, request)
        search_field = ExtractSearchFilterField().execute(model_admin, request)
        if search_field is not None:
            filter_fields = [search_field, *filter_fields]

        extract_editable_fields = ExtractEditableFields()

        return AdminModelResource(
            app_label=opts.app_label,
            model_name=opts.model_name,
            verbose_name=str(opts.verbose_name),
            verbose_name_plural=str(opts.verbose_name_plural),
            description=inspect.getdoc(type(model_admin)),
            each_model_actions=ExtractEachModelActions().execute(model_admin, request),
            app_level_actions=ExtractAppLevelActions().execute(model_admin, request),
            filter_fields=filter_fields,
            sortable_fields=ExtractSortableFields().execute(model_admin, request),
            list_per_page=model_admin.list_per_page,
            create_fields=extract_editable_fields.execute(model_admin, request, change=False),
            update_fields=extract_editable_fields.execute(model_admin, request, change=True),
            can_add=model_admin.has_add_permission(request),
            can_change=model_admin.has_change_permission(request),
            can_delete=model_admin.has_delete_permission(request),
        )
