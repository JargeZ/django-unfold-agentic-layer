from django.contrib.admin import ModelAdmin, SimpleListFilter, site
from django.http import HttpRequest
from django_unfold_agentic_layer.resources.actions.extract_list_filter_fields import (
    ExtractListFilterFields,
)
from server.apps.blog.models import BlogPost


def test_extract_list_filter_fields_from_field_names(
    blog_post_model_admin: ModelAdmin,
    admin_request: HttpRequest,
    blog_posts_by_two_authors: list[BlogPost],
    freezer,
    snapshot,
):
    # DateFieldListFilter's "Today"/"Past 7 days"/etc. choices are computed
    # relative to now() — freeze the clock so the snapshot is deterministic.
    freezer.move_to("2026-01-15T12:00:00+00:00")

    infos = ExtractListFilterFields().execute(blog_post_model_admin, admin_request)

    assert [info.model_dump() for info in infos] == snapshot


class _RecentFilter(SimpleListFilter):
    title = "recency"
    parameter_name = "recent"

    def lookups(self, request, model_admin):
        return [("today", "Today"), ("this_week", "This week")]

    def queryset(self, request, queryset):
        return queryset


def test_extract_list_filter_fields_from_tuple_and_custom_filter_class(
    admin_request: HttpRequest,
    blog_posts_by_two_authors: list[BlogPost],
    freezer,
    snapshot,
):
    freezer.move_to("2026-01-15T12:00:00+00:00")

    model_admin = ModelAdmin(BlogPost, site)
    # A SimpleListFilter subclass is field-independent, so — unlike a custom
    # FieldListFilter — it's registered as a bare class, never paired with a
    # field name in a tuple (that tuple form calls it with the wrong signature).
    model_admin.list_filter = ("author", "created_at", _RecentFilter)

    infos = ExtractListFilterFields().execute(model_admin, admin_request)

    assert [info.model_dump() for info in infos] == snapshot
