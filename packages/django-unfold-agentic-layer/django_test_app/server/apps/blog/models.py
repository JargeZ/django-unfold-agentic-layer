from django.conf import settings
from django.db import models


class BlogPost(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_posts",
    )
    # Nullable FK, distinct from `author` — exercises the `__isnull` half of
    # RelatedFieldListFilter's expected_parameters() and EditableFieldInfo's
    # "related" field type on an optional field.
    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="edited_blog_posts",
    )
    # Deliberately not blank=True despite the default: a Django ModelForm
    # applies a *blank* field's cleaned empty string to the instance outright
    # rather than falling back to the model-level default, so "optional with
    # a default" and "form-optional" aren't the same thing here.
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    # null=True (not just blank=True) matters here: an empty dict is one of
    # Django's default Field.empty_values, so a form round-trip of {} gets
    # cleaned to None — without null=True that violates the NOT NULL
    # constraint on save (a real Django JSONField gotcha, not MCP-specific).
    metadata = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title


class Comment(models.Model):
    """Not in the admin: only here so deleting a post can hit ``PROTECT``,
    with a ``__str__`` that follows the FK — formatting it from async
    context trips ``SynchronousOnlyOperation``."""

    post = models.ForeignKey(BlogPost, on_delete=models.PROTECT, related_name="comments")
    text = models.TextField()

    def __str__(self) -> str:
        return f"{self.post.title}: {self.text}"
