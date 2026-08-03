from django.apps import AppConfig
from django_unfold_agentic_layer.resources.actions.build_admin_app_resource import (
    BuildAdminAppResource,
)


def test_build_admin_app_resource(blog_app_config: AppConfig, snapshot):
    resource = BuildAdminAppResource().execute(blog_app_config)

    assert resource.model_dump() == snapshot
