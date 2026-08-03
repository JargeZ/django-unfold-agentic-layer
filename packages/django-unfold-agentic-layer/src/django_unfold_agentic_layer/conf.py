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
from typing import Any, Final, TypedDict, cast

from django.conf import settings

#: Name of the Django setting consuming projects override.
SETTINGS_NAME: Final = "UNFOLD_AGENTIC_LAYER"


@enum.unique
class Settings(enum.StrEnum):
    """Keys for all django_unfold_agentic_layer settings."""

    PORTAL_TITLE = "PORTAL_TITLE"


class SettingsDict(TypedDict, total=False):
    """Settings type that can be used for typing ``UNFOLD_AGENTIC_LAYER``."""

    PORTAL_TITLE: str


assert SettingsDict.__optional_keys__ == set(Settings), (
    "Settings enum and its type SettingsDict have different keys"
)

#: Default settings for django_unfold_agentic_layer.
DEFAULTS: Final[Mapping[Settings, Any]] = {
    Settings.PORTAL_TITLE: "Agentic Layer",
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


def get_config() -> SettingsDict:
    """Return :data:`DEFAULTS` merged with the project's ``UNFOLD_AGENTIC_LAYER``."""
    return cast(SettingsDict, _merge(DEFAULTS, getattr(settings, SETTINGS_NAME, {})))
