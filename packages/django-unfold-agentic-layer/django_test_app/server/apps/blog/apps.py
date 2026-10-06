from django.apps import AppConfig


class BlogConfig(AppConfig):
    """Simple blog app used to exercise the admin resource-generation module in tests."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "server.apps.blog"
    label = "blog"
    verbose_name = "Blog"
