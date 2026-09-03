from django.contrib.admin import ModelAdmin
from django.http import HttpRequest
from django_unfold_agentic_layer.resources.actions.build_admin_model_resource import (
    BuildAdminModelResource,
)
from server.apps.blog.models import BlogPost


def test_build_admin_model_resource(
    blog_post_model_admin: ModelAdmin,
    admin_request: HttpRequest,
    blog_posts_by_two_authors: list[BlogPost],
    freezer,
    snapshot,
):
    freezer.move_to("2026-01-15T12:00:00+00:00")

    resource = BuildAdminModelResource().execute(blog_post_model_admin, admin_request)

    assert resource.model_dump() == snapshot
