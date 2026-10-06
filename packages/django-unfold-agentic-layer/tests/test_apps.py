from django.apps import apps


def test_app_is_registered():
    config = apps.get_app_config("django_unfold_agentic_layer")

    assert config.name == "django_unfold_agentic_layer"
    assert config.label == "django_unfold_agentic_layer"


def test_package_imports_cleanly():
    import django_unfold_agentic_layer

    assert django_unfold_agentic_layer.__version__
