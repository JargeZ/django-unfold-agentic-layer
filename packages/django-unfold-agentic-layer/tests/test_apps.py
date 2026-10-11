from django.apps import apps


def test_app_is_registered():
    config = apps.get_app_config("django_unfold_agentic_layer")

    assert config.name == "django_unfold_agentic_layer"
    assert config.label == "django_unfold_agentic_layer"


def test_package_imports_cleanly():
    import django_unfold_agentic_layer

    assert django_unfold_agentic_layer.__version__


def _warning_ids(**kwargs) -> set[str]:
    from django.core.checks import run_checks

    return {message.id for message in run_checks(**kwargs)}


def test_deploy_check_warns_about_a_per_process_confirmation_cache(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    assert "django_unfold_agentic_layer.W001" in _warning_ids(include_deployment_checks=True)

    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    assert "django_unfold_agentic_layer.W001" not in _warning_ids(include_deployment_checks=True)


def test_check_warns_while_unauthorized_mode_is_on(settings):
    settings.DEBUG = True
    settings.UNFOLD_AGENTIC_LAYER_UNAUTHORIZED = True
    assert "django_unfold_agentic_layer.W002" in _warning_ids()

    settings.DEBUG = False
    assert "django_unfold_agentic_layer.W002" not in _warning_ids()
