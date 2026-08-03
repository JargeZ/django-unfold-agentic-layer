from django.contrib.admin import ModelAdmin, SimpleListFilter, site
from django_unfold_agentic_layer.resources.actions.extract_list_filter_fields import (
    ExtractListFilterFields,
)
from server.apps.blog.models import BlogPost


def test_extract_list_filter_fields_from_field_names(blog_post_model_admin: ModelAdmin, snapshot):
    infos = ExtractListFilterFields().execute(blog_post_model_admin)

    assert [info.model_dump() for info in infos] == snapshot


class _RecentFilter(SimpleListFilter):
    title = "recency"
    parameter_name = "recent"

    def lookups(self, request, model_admin):
        return []

    def queryset(self, request, queryset):
        return queryset


def test_extract_list_filter_fields_from_tuple_and_custom_filter_class(snapshot):
    model_admin = ModelAdmin(BlogPost, site)
    model_admin.list_filter = ("author", ("created_at", _RecentFilter), _RecentFilter)

    infos = ExtractListFilterFields().execute(model_admin)

    assert [info.model_dump() for info in infos] == snapshot
