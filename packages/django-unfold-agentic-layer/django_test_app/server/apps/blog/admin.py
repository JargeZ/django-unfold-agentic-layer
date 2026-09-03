from django.contrib import admin
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.urls import reverse
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter
from unfold.decorators import action

from .models import BlogPost

admin.site.unregister(User)


@admin.register(User)
class UnfoldUserAdmin(ModelAdmin):
    # Required for AutocompleteSelectFilter (used below on BlogPostAdmin) —
    # it drives its AJAX widget through this admin's own search_results.
    search_fields = ("username", "email")


@admin.action(description="Publish selected blog posts")
def publish_posts(model_admin, request, queryset):
    pass


class HasEditorFilter(admin.SimpleListFilter):
    """Field-independent custom filter — exercises the "parameter exists,
    lookup_choices exist, but no underlying model field" branch of filter
    schema extraction (see ExtractListFilterFields)."""

    title = "has editor"
    parameter_name = "has_editor"

    def lookups(self, request, model_admin):
        return [("yes", "Has editor"), ("no", "No editor")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(editor__isnull=True)
        if self.value() == "no":
            return queryset.filter(editor__isnull=True)
        return queryset


@admin.register(BlogPost)
class BlogPostAdmin(ModelAdmin):
    list_display = ("title", "author", "status", "is_featured", "created_at")
    list_filter = (
        "author",
        ("editor", AutocompleteSelectFilter),
        HasEditorFilter,
        "status",
        "is_featured",
        "created_at",
    )
    search_fields = ("title", "body")
    actions = (publish_posts,)

    # Unfold's own action placements — one of each supported kind, per
    # https://unfoldadmin.com/docs/actions/changelist/
    actions_list = ("export_all_posts",)
    actions_row = ("feature_post",)
    actions_detail = ("archive_post",)
    actions_submit_line = ("notify_author_on_save",)

    @action(description="Export all posts")
    def export_all_posts(self, request):
        return HttpResponseRedirect(reverse("admin:blog_blogpost_changelist"))

    @action(description="Feature this post")
    def feature_post(self, request, object_id):
        return HttpResponseRedirect(reverse("admin:blog_blogpost_changelist"))

    @action(description="Archive this post")
    def archive_post(self, request, object_id):
        return HttpResponseRedirect(reverse("admin:blog_blogpost_change", args=[object_id]))

    @action(description="Notify author on save")
    def notify_author_on_save(self, request, obj):
        pass
