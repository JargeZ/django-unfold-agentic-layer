import csv

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import path, reverse
from djangoql.admin import DjangoQLSearchMixin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter
from unfold.decorators import action, display
from unfold.enums import ActionVariant
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .forms import AppendNoteDialogForm, BlogPostActionForm, DraftDialogForm, SetStatusDialogForm
from .models import BlogPost

admin.site.unregister(User)


@admin.register(User)
class UnfoldUserAdmin(BaseUserAdmin, ModelAdmin):
    # https://unfoldadmin.com/docs/installation/auth/ — Django's own UserAdmin
    # (fieldsets, masked password hash, add_form) on Unfold's forms. Its
    # search_fields also drive AutocompleteSelectFilter on BlogPostAdmin below.
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.action(description="Publish selected blog posts")
def publish_posts(model_admin, request, queryset):
    count = queryset.update(status=BlogPost.Status.PUBLISHED)
    model_admin.message_user(request, f"Published {count} post(s).", messages.SUCCESS)


@admin.action(description="Assign editor to selected posts")
def assign_editor(model_admin, request, queryset):
    # Reads BlogPostActionForm's extra field, the classic Django way.
    queryset.update(editor_id=request.POST.get("editor") or None)
    model_admin.message_user(request, f"Updated {queryset.count()} post(s).")


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
class BlogPostAdmin(DjangoQLSearchMixin, ModelAdmin):
    list_display = ("title", "author", "status", "is_featured", "created_at")
    list_filter = (
        "author",
        ("editor", AutocompleteSelectFilter),
        HasEditorFilter,
        "status",
        "is_featured",
        "created_at",
    )
    # Own search_fields next to DjangoQLSearchMixin: the admin shows a
    # plain/DjangoQL toggle (q-l=on), see ExtractSearchFilterField.
    search_fields = ("title", "body")
    # Computed admin method on the changeform — not a model attribute.
    readonly_fields = ("word_count",)
    # Every action kind Unfold supports — https://unfoldadmin.com/docs/actions/
    # Bulk (changelist select box): plain Django actions, one reading the
    # extra action_form field, and an Unfold @action with a variant.
    action_form = BlogPostActionForm
    actions = (publish_posts, assign_editor, "archive_selected")
    # Changelist top, incl. a dropdown group.
    actions_list = ("export_all_posts", {"title": "More", "items": ("create_draft",)})
    # Each changelist row; feature_post is also a detail action (one tool).
    actions_row = ("feature_post", "set_status")
    # Changeform top, incl. a dropdown group.
    actions_detail = (
        "feature_post",
        "publish_post",
        {"title": "More", "items": ("append_note",)},
        "pin_post",
    )
    # Runs while saving the changeform — not exposed over MCP yet.
    actions_submit_line = ("notify_author_on_save",)

    @display(description="Word count")
    def word_count(self, obj):
        return len(obj.body.split())

    @action(
        description="Archive selected posts",
        permissions=["change"],
        variant=ActionVariant.DANGER,
        icon="archive",
    )
    def archive_selected(self, request, queryset):
        count = queryset.update(status=BlogPost.Status.ARCHIVED)
        self.message_user(request, f"Archived {count} post(s).", messages.WARNING)

    @action(description="Export all posts", icon="download")
    def export_all_posts(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="posts.csv"'
        writer = csv.writer(response)
        writer.writerow(["id", "title", "status"])
        for post in self.get_queryset(request).order_by("pk"):
            writer.writerow([post.pk, post.title, post.status])
        return response

    @action(
        description="Create draft",
        icon="add",
        dialog={
            "title": "New draft",
            "description": "Creates an empty draft authored by you.",
            "form_class": DraftDialogForm,
        },
    )
    def create_draft(self, request, form):
        post = BlogPost.objects.create(title=form.cleaned_data["title"], author=request.user)
        self.message_user(request, f"Created draft {post.title!r}.", messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:blog_blogpost_change", args=[post.pk]))

    @action(description="Feature this post", icon="star")
    def feature_post(self, request, object_id):
        BlogPost.objects.filter(pk=object_id).update(is_featured=True)
        self.message_user(request, "Post featured.", messages.SUCCESS)
        # Like Unfold's docs: assumes a browser, which always sends a Referer.
        return redirect(request.headers["referer"])

    @action(
        description="Set status",
        dialog={"title": "Change status", "form_class": SetStatusDialogForm},
    )
    def set_status(self, request, form, object_id):
        BlogPost.objects.filter(pk=object_id).update(status=form.cleaned_data["status"])
        return HttpResponseRedirect(reverse("admin:blog_blogpost_changelist"))

    @action(description="Publish this post", permissions=["publish"], variant=ActionVariant.PRIMARY)
    def publish_post(self, request, object_id):
        BlogPost.objects.filter(pk=object_id).update(status=BlogPost.Status.PUBLISHED)
        return HttpResponseRedirect(reverse("admin:blog_blogpost_change", args=[object_id]))

    def has_publish_permission(self, request, obj=None):
        # Custom permission method — only superusers may publish directly.
        return request.user.is_superuser

    @action(
        description="Append note",
        dialog={"title": "Append note", "form_class": AppendNoteDialogForm},
    )
    def append_note(self, request, form, object_id):
        post = BlogPost.objects.get(pk=object_id)
        post.body = f"{post.body}\n\n{form.cleaned_data['note']}".strip()
        post.save(update_fields=["body"])
        return HttpResponseRedirect(reverse("admin:blog_blogpost_change", args=[object_id]))

    @action(description="Save and notify author", icon="send")
    def notify_author_on_save(self, request, obj):
        self.message_user(request, f"Author {obj.author} notified.")

    # Like django-unfold's own docs, a detail action whose permission method
    # *requires* object_id — undecidable without an instance, so it must not
    # take the whole admin out of MCP.
    @action(description="Pin this post", permissions=["pin"])
    def pin_post(self, request, object_id):
        BlogPost.objects.filter(pk=object_id).update(is_featured=True)
        return HttpResponseRedirect(reverse("admin:blog_blogpost_change", args=[object_id]))

    def has_pin_permission(self, request, object_id):
        return BlogPost.objects.filter(pk=object_id, author=request.user).exists()


class SiteSettings:
    """Not a Django model: a stand-in class an admin registers for a custom
    settings page, the way django-constance registers its ``Config``."""

    class Meta:
        app_label = "blog"
        object_name = "SiteSettings"
        model_name = "sitesettings"
        verbose_name_plural = "site settings"
        abstract = False
        swapped = False
        is_composite_pk = False
        concrete_model = None

        @property
        def app_config(self):
            from django.apps import apps

            return apps.get_app_config(self.app_label)

    _meta = Meta()


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    actions_list = ("clear_cache",)

    def get_urls(self):
        view = self.admin_site.admin_view(self.changelist_view)
        return [path("", view, name="blog_sitesettings_changelist")]

    @action(description="Clear cache")
    def clear_cache(self, request):
        self.message_user(request, "Cache cleared.", messages.SUCCESS)
        return redirect(request.headers["referer"])
