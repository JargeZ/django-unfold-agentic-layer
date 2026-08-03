from django.contrib import admin
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.urls import reverse
from unfold.admin import ModelAdmin
from unfold.decorators import action

from .models import BlogPost

admin.site.unregister(User)


@admin.register(User)
class UnfoldUserAdmin(ModelAdmin):
    pass


@admin.action(description="Publish selected blog posts")
def publish_posts(model_admin, request, queryset):
    pass


@admin.register(BlogPost)
class BlogPostAdmin(ModelAdmin):
    list_display = ("title", "author", "created_at")
    list_filter = ("author", "created_at")
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
