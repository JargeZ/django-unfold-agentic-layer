from django.contrib.admin import ModelAdmin, site
from django.http import HttpRequest
from django_unfold_agentic_layer.resources.actions.extract_search_filter_field import (
    ExtractSearchFilterField,
)
from server.apps.blog.models import BlogPost


def test_extract_search_filter_field_when_search_enabled(
    blog_post_model_admin: ModelAdmin, admin_request: HttpRequest, snapshot
):
    info = ExtractSearchFilterField().execute(blog_post_model_admin, admin_request)

    assert info is not None
    assert info.model_dump() == snapshot


def test_extract_search_filter_field_when_search_disabled(admin_request: HttpRequest):
    model_admin = ModelAdmin(BlogPost, site)
    model_admin.search_fields = ()

    assert ExtractSearchFilterField().execute(model_admin, admin_request) is None
