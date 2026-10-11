from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.locmem import LocMemCache
from django.core.checks import Warning, register

from django_unfold_agentic_layer.conf import Settings, get_config


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
