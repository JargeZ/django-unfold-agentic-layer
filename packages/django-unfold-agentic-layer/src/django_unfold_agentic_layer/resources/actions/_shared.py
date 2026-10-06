"""Small helpers shared by the action-extraction actions in this package.

Not an action itself — just avoids repeating the same "resolved action" →
:class:`ActionInfo` conversion for both of Django's and django-unfold's own
action representations.
"""

from collections.abc import Callable
from typing import Any

from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import model_format_dict
from django.http import HttpRequest

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


def get_filtered_unfold_actions(
    model_admin: ModelAdmin,
    request: HttpRequest,
    getter_name: str,
    object_id: int | str | None = None,
) -> list[Any]:
    """Call one of django-unfold's permission-filtered ``get_actions_*`` methods.

    ``get_actions_detail``/``get_actions_submit_line`` are instance-scoped
    (their object-level permission checks need an ``object_id``); at the
    model-description level there is no specific instance yet, so
    ``object_id=None`` is passed through — django-unfold's own
    ``_filter_unfold_actions_by_permissions`` treats a missing ``object_id``
    as "check the non-object form of the permission", which is exactly the
    best-effort answer a model-level (not instance-level) description can give.
    Returns ``[]`` for a plain ``ModelAdmin`` that isn't django-unfold's.
    """
    getter = getattr(model_admin, getter_name, None)
    if getter is None:
        return []
    if getter_name in ("get_actions_detail", "get_actions_submit_line"):
        return list(getter(request, object_id))
    return list(getter(request))
