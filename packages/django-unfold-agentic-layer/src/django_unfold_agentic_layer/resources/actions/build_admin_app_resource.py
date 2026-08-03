import inspect

from django.apps import AppConfig
from django.contrib.admin import AdminSite
from django.contrib.admin import site as default_admin_site

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions.build_admin_model_resource import (
    BuildAdminModelResource,
)
from django_unfold_agentic_layer.resources.schemas import AdminAppResource


class BuildAdminAppResource(BaseLogicAction):
    """A Django app section of the admin, with every model registered in it.

    ``description`` comes from the app's ``AppConfig`` docstring — Django has
    no dedicated field for it, and the docstring is where a developer would
    naturally document what the app is for.
    """

    def execute(
        self, app_config: AppConfig, admin_site: AdminSite = default_admin_site
    ) -> AdminAppResource:
        build_model_resource = BuildAdminModelResource()
        models = [
            build_model_resource.execute(model_admin)
            for model, model_admin in admin_site._registry.items()
            if model._meta.app_label == app_config.label
        ]

        return AdminAppResource(
            title=str(app_config.verbose_name),
            description=inspect.getdoc(type(app_config)),
            models=models,
        )
