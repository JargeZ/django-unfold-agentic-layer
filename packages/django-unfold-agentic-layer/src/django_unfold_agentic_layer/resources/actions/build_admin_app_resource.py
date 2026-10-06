import inspect

from django.apps import AppConfig
from django.contrib.admin import AdminSite
from django.contrib.admin import site as default_admin_site
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions.build_admin_model_resource import (
    BuildAdminModelResource,
)
from django_unfold_agentic_layer.resources.schemas import AdminAppResource


class BuildAdminAppResource(BaseLogicAction):
    """A Django app section of the admin, with every model registered in it
    that ``request.user`` has any permission on.

    ``description`` comes from the app's ``AppConfig`` docstring — Django has
    no dedicated field for it, and the docstring is where a developer would
    naturally document what the app is for.

    Permission filtering reuses ``AdminSite._build_app_dict`` — the same
    module/model-permission check the admin's own app index page runs —
    rather than a bespoke filter step, so a model without ``has_module_permission``
    or any of ``add``/``change``/``delete``/``view`` simply doesn't appear.
    """

    def execute(
        self,
        app_config: AppConfig,
        request: HttpRequest,
        admin_site: AdminSite = default_admin_site,
    ) -> AdminAppResource:
        app_dict = admin_site._build_app_dict(request, label=app_config.label)
        model_dicts = app_dict[app_config.label]["models"] if app_config.label in app_dict else []

        build_model_resource = BuildAdminModelResource()
        models = [
            build_model_resource.execute(admin_site._registry[model_dict["model"]], request)
            for model_dict in model_dicts
        ]

        return AdminAppResource(
            title=str(app_config.verbose_name),
            description=inspect.getdoc(type(app_config)),
            models=models,
        )
