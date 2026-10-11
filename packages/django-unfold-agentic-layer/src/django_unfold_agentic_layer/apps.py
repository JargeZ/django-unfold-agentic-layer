from django.apps import AppConfig


class DjangoUnfoldAgenticLayerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_unfold_agentic_layer"
    label = "django_unfold_agentic_layer"
    verbose_name = "Django Unfold Agentic Layer"

    def ready(self):
        from django_unfold_agentic_layer import checks  # noqa: F401 — registers them
