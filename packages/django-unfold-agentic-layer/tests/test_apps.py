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


def test_deploy_check_warns_when_use_mcp_is_not_required(settings):
    settings.UNFOLD_AGENTIC_LAYER = {"REQUIRED_PERMISSION": False}
    assert "django_unfold_agentic_layer.W003" in _warning_ids(include_deployment_checks=True)

    settings.UNFOLD_AGENTIC_LAYER = {}
    assert "django_unfold_agentic_layer.W003" not in _warning_ids(include_deployment_checks=True)


def test_startup_logs_insecure_settings(settings, caplog):
    """gunicorn and uvicorn run no system checks: the warnings are logged too."""
    from django_unfold_agentic_layer.checks import log_startup_warnings

    settings.DEBUG = True
    settings.UNFOLD_AGENTIC_LAYER_UNAUTHORIZED = True
    log_startup_warnings()
    settings.SILENCED_SYSTEM_CHECKS = ["django_unfold_agentic_layer.W002"]
    log_startup_warnings()

    logged = [
        r.getMessage() for r in caplog.records if r.name == "django_unfold_agentic_layer.config"
    ]
    assert len(logged) == 1
    assert logged[0].startswith(
        "django_unfold_agentic_layer.W002 UNFOLD_AGENTIC_LAYER_UNAUTHORIZED"
    )
