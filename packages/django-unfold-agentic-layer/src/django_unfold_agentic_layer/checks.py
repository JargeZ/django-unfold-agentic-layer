from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.locmem import LocMemCache
from django.core.checks import Warning, register

from django_unfold_agentic_layer import log
from django_unfold_agentic_layer.conf import Settings, get_config, is_model_exposed


@register(deploy=True)
def check_confirmation_cache(app_configs, **kwargs):
    alias = get_config()[Settings.CONFIRMATION_CACHE]
    if not isinstance(caches[alias], LocMemCache):
        return []
    return [
        Warning(
            f"UNFOLD_AGENTIC_LAYER['CONFIRMATION_CACHE'] ({alias!r}) is a per-process "
            "LocMemCache: with several workers, one delete/action confirmation can be "
            "used once per worker.",
            hint="Point CONFIRMATION_CACHE at a cache all workers share (Redis, database…).",
            id="django_unfold_agentic_layer.W001",
        )
    ]


@register
def check_unauthorized_mode(app_configs, **kwargs):
    if not (settings.DEBUG and getattr(settings, "UNFOLD_AGENTIC_LAYER_UNAUTHORIZED", False)):
        return []
    return [
        Warning(
            "UNFOLD_AGENTIC_LAYER_UNAUTHORIZED is on: /mcp/ accepts requests without a "
            "token and runs them as the first active superuser.",
            hint="Local development only — never on a reachable host.",
            id="django_unfold_agentic_layer.W002",
        )
    ]


@register(deploy=True)
def check_required_permission(app_configs, **kwargs):
    if get_config()[Settings.REQUIRED_PERMISSION]:
        return []
    return [
        Warning(
            "UNFOLD_AGENTIC_LAYER['REQUIRED_PERMISSION'] is False: every active staff user "
            "may log in to MCP, not only users with django_unfold_agentic_layer.use_mcp.",
            hint="Keep it True and grant use_mcp to the users or groups that need MCP.",
            id="django_unfold_agentic_layer.W003",
        )
    ]


@register(deploy=True)
def check_exposed_models(app_configs, **kwargs):
    user_model = settings.AUTH_USER_MODEL.lower()
    exposed = [label for label in (user_model, "auth.group") if is_model_exposed(*label.split("."))]
    if not exposed:
        return []
    return [
        Warning(
            f"UNFOLD_AGENTIC_LAYER['MODELS'] exposes {', '.join(exposed)} to MCP: an agent "
            "with change permission there can grant permissions or superuser status.",
            hint="Leave MODELS['EXCLUDE'] at None, or list these models in it.",
            id="django_unfold_agentic_layer.W004",
        )
    ]


def log_startup_warnings() -> None:
    """Logs this app's check warnings once, at startup: ``runserver`` and
    ``migrate`` run system checks, but gunicorn and uvicorn do not. Deploy
    checks join in when ``DEBUG`` is off; ``SILENCED_SYSTEM_CHECKS`` applies."""
    checks = [check_unauthorized_mode]
    if not settings.DEBUG:
        checks += [check_confirmation_cache, check_required_permission, check_exposed_models]
    for check in checks:
        for message in check(None):
            if message.id not in settings.SILENCED_SYSTEM_CHECKS:
                log.config.warning("%s %s %s", message.id, message.msg, message.hint)
