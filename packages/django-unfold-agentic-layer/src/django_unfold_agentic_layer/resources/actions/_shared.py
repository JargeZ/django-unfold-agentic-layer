"""Small helpers shared by the action-extraction actions in this package.

Not an action itself — just avoids repeating the same "resolved action" →
:class:`ActionInfo` conversion for both of Django's and django-unfold's own
action representations.
"""

from collections.abc import Callable
from typing import Any

from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import model_format_dict
from django.db.models import Model
from django.http import HttpRequest

from django_unfold_agentic_layer.resources.schemas import ActionInfo

#: What ``ModelAdmin.get_action()`` returns: (callable, name, description).
ResolvedDjangoAction = tuple[Callable, str, str]


def is_django_model(model: Any) -> bool:
    """Admins may register a stand-in class instead of a model (e.g.
    django-constance's ``Config``): it has ``_meta`` but no queryset."""
    return isinstance(model, type) and issubclass(model, Model)


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
    model_admin: ModelAdmin, request: HttpRequest, getter_name: str
) -> list[Any]:
    """The actions of one of django-unfold's ``get_actions_*`` getters that
    ``request.user`` may run, decided without a specific instance.

    Each action goes through django-unfold's own
    ``_filter_unfold_actions_by_permissions`` on its own: with no
    ``object_id`` it calls ``has_<perm>_permission(request)``, so a check
    that *requires* ``object_id`` raises ``TypeError``. Such an action stays
    listed — it can't be decided at model level, and the action's
    ``@action(permissions=…)`` decorator re-checks it on the real instance at
    run time. One such check never hides the rest of the admin.
    Returns ``[]`` for a plain ``ModelAdmin`` that isn't django-unfold's.
    """
    base_getter = getattr(model_admin, getter_name.replace("get_", "_get_base_", 1), None)
    if base_getter is None:
        return []
    allowed = []
    for action in base_getter():
        try:
            allowed += model_admin._filter_unfold_actions_by_permissions(request, [action])
        except TypeError:
            allowed.append(action)
    return allowed
