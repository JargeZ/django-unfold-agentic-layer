from django.apps import AppConfig
from django.http import HttpRequest
from django_unfold_agentic_layer.resources.actions.build_admin_app_resource import (
    BuildAdminAppResource,
)
from server.apps.blog.models import BlogPost


def test_build_admin_app_resource(
    blog_app_config: AppConfig,
    admin_request: HttpRequest,
    blog_posts_by_two_authors: list[BlogPost],
    freezer,
    snapshot,
):
    freezer.move_to("2026-01-15T12:00:00+00:00")

    resource = BuildAdminAppResource().execute(blog_app_config, admin_request)

    assert resource.model_dump() == snapshot
