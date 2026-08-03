from django.contrib.admin import ModelAdmin, site
from django_unfold_agentic_layer.resources.actions.extract_search_filter_field import (
    ExtractSearchFilterField,
)
from server.apps.blog.models import BlogPost


def test_extract_search_filter_field_when_search_enabled(
    blog_post_model_admin: ModelAdmin, snapshot
):
    info = ExtractSearchFilterField().execute(blog_post_model_admin)

    assert info is not None
    assert info.model_dump() == snapshot


def test_extract_search_filter_field_when_search_disabled():
    model_admin = ModelAdmin(BlogPost, site)
    model_admin.search_fields = ()

    assert ExtractSearchFilterField().execute(model_admin) is None
