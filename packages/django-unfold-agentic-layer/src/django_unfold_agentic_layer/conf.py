"""Default settings for django_unfold_agentic_layer.

Two patterns borrowed directly from sibling projects in this ecosystem:

* the dict-override merge is Unfold's own (see ``unfold.settings.get_config``) —
  consuming projects declare a same-named ``UNFOLD_AGENTIC_LAYER`` dict, and any key
  they omit falls back to its default; nested dicts are merged, not replaced.
* the enum + ``TypedDict`` pair is ``django-modern-rest``'s (see ``dmr.settings``) —
  ``Settings`` gives every key a name to import and reference instead of a bare
  string, ``SettingsDict`` types the dict itself, and the two asserts below keep
  them (and :data:`DEFAULTS`) from drifting apart.
"""

import enum
from collections.abc import Mapping
from datetime import timedelta
from typing import Any, Final, TypedDict, cast

from django.conf import settings

#: Name of the Django setting consuming projects override.
SETTINGS_NAME: Final = "UNFOLD_AGENTIC_LAYER"


@enum.unique
class Settings(enum.StrEnum):
    """Keys for all django_unfold_agentic_layer settings."""

    PORTAL_TITLE = "PORTAL_TITLE"
    #: Lifetime of an MCP OAuth access token; once it expires the client
    #: re-runs the browser login flow (no refresh tokens are issued).
    SESSION_TTL = "SESSION_TTL"
    #: Alias in ``CACHES`` that remembers already-answered confirmation rounds
    #: (replay protection). Must be shared by every worker process.
    CONFIRMATION_CACHE = "CONFIRMATION_CACHE"
    #: ``True`` turns off open RFC 7591 registration: ``/register`` refuses,
    #: and an admin adds each MCP client by hand (admin → MCP clients → Add),
    #: then gives its client ID to the person who connects.
    CLOSED_CLIENT_REGISTRATION = "CLOSED_CLIENT_REGISTRATION"
    #: ``True``: only users holding ``django_unfold_agentic_layer.use_mcp``
    #: (superusers always do) may log in and use ``/mcp``. ``False``: every
    #: active staff user may.
    REQUIRED_PERMISSION = "REQUIRED_PERMISSION"
    #: Which admin models MCP exposes, as ``{"INCLUDE": [...], "EXCLUDE": [...]}``
    #: of ``"app_label"`` or ``"app_label.model"`` entries. ``INCLUDE: None`` is
    #: every model; ``EXCLUDE: None`` is the user model and ``auth.group``, so an
    #: agent can't grant permissions or superuser status. ``[]`` excludes none.
    MODELS = "MODELS"
    #: ``True``: create/update tools and every admin action ask the user to
    #: confirm before they run, like delete tools and ``DANGER`` actions do.
    CONFIRM_WRITES = "CONFIRM_WRITES"


class ModelsDict(TypedDict, total=False):
    """``MODELS``: entries are ``"app_label"`` or ``"app_label.model"``."""

    INCLUDE: list[str] | None
    EXCLUDE: list[str] | None


class SettingsDict(TypedDict, total=False):
    """Settings type that can be used for typing ``UNFOLD_AGENTIC_LAYER``."""

    PORTAL_TITLE: str
    SESSION_TTL: timedelta
    CONFIRMATION_CACHE: str
    CLOSED_CLIENT_REGISTRATION: bool
    REQUIRED_PERMISSION: bool
    MODELS: "ModelsDict"
    CONFIRM_WRITES: bool


assert SettingsDict.__optional_keys__ == set(Settings), (
    "Settings enum and its type SettingsDict have different keys"
)

#: Default settings for django_unfold_agentic_layer.
DEFAULTS: Final[Mapping[Settings, Any]] = {
    Settings.PORTAL_TITLE: "Agentic Layer",
    Settings.SESSION_TTL: timedelta(days=1),
    Settings.CONFIRMATION_CACHE: "default",
    Settings.CLOSED_CLIENT_REGISTRATION: False,
    Settings.REQUIRED_PERMISSION: True,
    Settings.MODELS: {"INCLUDE": None, "EXCLUDE": None},
    Settings.CONFIRM_WRITES: False,
}

assert all(setting_key in DEFAULTS for setting_key in Settings), (
    "Some Settings keys do not have default values"
)


def _merge(defaults: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)

    for key, value in overrides.items():
        if isinstance(merged.get(key), Mapping) and isinstance(value, Mapping):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value

    return merged


def is_model_exposed(app_label: str, model_name: str) -> bool:
    """Whether ``MODELS`` lets MCP expose this admin model."""
    models = get_config()[Settings.MODELS]
    exclude = models.get("EXCLUDE")
    if exclude is None:
        exclude = [settings.AUTH_USER_MODEL, "auth.group"]
    include = models.get("INCLUDE")

    def matches(entries: list[str]) -> bool:
        names = {entry.lower() for entry in entries}
        return app_label.lower() in names or f"{app_label}.{model_name}".lower() in names

    return (include is None or matches(include)) and not matches(exclude)


def get_config() -> SettingsDict:
    """Return :data:`DEFAULTS` merged with the project's ``UNFOLD_AGENTIC_LAYER``."""
    return cast(SettingsDict, _merge(DEFAULTS, getattr(settings, SETTINGS_NAME, {})))
