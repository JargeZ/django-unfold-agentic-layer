from django.contrib.admin import ModelAdmin
from django_unfold_agentic_layer.resources.actions.build_admin_model_resource import (
    BuildAdminModelResource,
)


def test_build_admin_model_resource(blog_post_model_admin: ModelAdmin, snapshot):
    resource = BuildAdminModelResource().execute(blog_post_model_admin)

    assert resource.model_dump() == snapshot
