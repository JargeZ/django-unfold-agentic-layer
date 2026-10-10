from django.contrib.admin import ModelAdmin, site
from django.http import HttpRequest
from django_unfold_agentic_layer.resources.actions.extract_search_filter_field import (
    ExtractSearchFilterField,
)
from djangoql.admin import DjangoQLSearchMixin
from server.apps.blog.models import BlogPost


def test_extract_search_filter_field_with_djangoql_toggle(
    blog_post_model_admin: ModelAdmin, admin_request: HttpRequest, snapshot
):
    fields = ExtractSearchFilterField().execute(blog_post_model_admin, admin_request)

    assert [field.model_dump() for field in fields] == snapshot


def test_extract_search_filter_field_without_djangoql(admin_request: HttpRequest, snapshot):
    model_admin = ModelAdmin(BlogPost, site)
    model_admin.search_fields = ("title",)

    fields = ExtractSearchFilterField().execute(model_admin, admin_request)

    assert [field.model_dump() for field in fields] == snapshot


def test_extract_search_filter_field_djangoql_only(admin_request: HttpRequest, snapshot):
    class DjangoQLOnlyAdmin(DjangoQLSearchMixin, ModelAdmin):
        pass

    fields = ExtractSearchFilterField().execute(DjangoQLOnlyAdmin(BlogPost, site), admin_request)

    assert [field.model_dump() for field in fields] == snapshot


def test_extract_search_filter_field_when_search_disabled(admin_request: HttpRequest):
    model_admin = ModelAdmin(BlogPost, site)
    model_admin.search_fields = ()

    assert ExtractSearchFilterField().execute(model_admin, admin_request) == []
