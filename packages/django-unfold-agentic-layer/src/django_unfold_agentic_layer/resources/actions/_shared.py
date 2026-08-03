"""Small helpers shared by the action-extraction actions in this package.

Not an action itself — just avoids repeating the same "resolved action" →
:class:`ActionInfo` conversion for both of Django's and django-unfold's own
action representations.
"""

from collections.abc import Callable
from typing import Any

from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import model_format_dict

from django_unfold_agentic_layer.resources.schemas import ActionInfo

#: What ``ModelAdmin.get_action()`` returns: (callable, name, description).
ResolvedDjangoAction = tuple[Callable, str, str]


def django_action_to_info(model_admin: ModelAdmin, resolved: ResolvedDjangoAction) -> ActionInfo:
    _func, key, description = resolved
    title = str(description) % model_format_dict(model_admin.opts)
    return ActionInfo(key=key, title=title)


def unfold_action_to_info(action: Any) -> ActionInfo:
    """``action`` is an ``unfold.dataclasses.UnfoldAction``.

    Its ``action_name`` is already the app/model-qualified identifier
    django-unfold itself registers the action's URL under.
    """
    return ActionInfo(key=action.action_name, title=str(action.description))


def get_base_unfold_actions(model_admin: ModelAdmin, getter_name: str) -> list[Any]:
    """Call one of django-unfold's ``_get_base_actions_*`` methods, if present.

    These return the raw, unfiltered-by-permission action list straight from
    django-unfold's own storage — exactly what a static resource description
    needs. Returns ``[]`` for a plain ``ModelAdmin`` that isn't django-unfold's.
    """
    getter = getattr(model_admin, getter_name, None)
    return list(getter()) if getter is not None else []
