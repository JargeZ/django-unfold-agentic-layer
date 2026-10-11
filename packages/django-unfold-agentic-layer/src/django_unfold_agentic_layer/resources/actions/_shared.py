"""Small helpers shared by the action-extraction actions in this package.

Not an action itself — just avoids repeating the same "resolved action" →
:class:`ActionInfo` conversion for both of Django's and django-unfold's own
action representations.
"""

from collections.abc import Callable, Mapping
from typing import Any

from django import forms
from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import model_format_dict
from django.contrib.messages.storage.base import BaseStorage
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


def splits_into_subwidgets(widget: forms.Widget) -> bool:
    """A ``MultiWidget`` that reads its value from ``<name><suffix>`` keys
    (``widgets_names``): Money, split datetime, range. A subclass with its
    own ``value_from_datadict`` (Unfold's ``ArrayWidget``) is excluded."""
    return (
        isinstance(widget, forms.MultiWidget)
        and type(widget).value_from_datadict is forms.MultiWidget.value_from_datadict
    )


def to_form_data(fields: Mapping[str, forms.Field], values: dict[str, Any]) -> dict[str, Any]:
    """Field values -> the keys a bound form reads. A composite field's
    value goes to one key per subwidget: a list as is, any other value
    (a model value, e.g. ``Money``/``datetime``) through the widget's own
    ``decompress()``, as Django does to render it."""
    data = {}
    for name, value in values.items():
        field = fields.get(name)
        if field is None or not splits_into_subwidgets(field.widget):
            data[name] = value
            continue
        widget = field.widget
        parts = value if isinstance(value, list | tuple) else widget.decompress(value)
        data.update({f"{name}{suffix}": part for suffix, part in zip(widget.widgets_names, parts)})
    return data


class CollectedMessages(BaseStorage):
    """In-memory ``django.contrib.messages`` storage: captures what an
    admin view reports, without persisting it into the MCP response's
    session/cookies the way the real storage backends would."""

    def _get(self, *args: Any, **kwargs: Any) -> tuple[list, bool]:
        return [], True

    def _store(self, messages: list, response: Any, *args: Any, **kwargs: Any) -> list:
        return []
