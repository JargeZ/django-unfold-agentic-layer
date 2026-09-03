from django.contrib.admin import ModelAdmin
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction


class ExtractSortableFields(BaseLogicAction):
    """Field names an agent may pass as ``order_by`` — the intersection of
    ``get_sortable_by()`` and ``get_list_display()``, in ``list_display`` order
    (that order becomes the ``Literal`` choice order on the generated tool).

    Only names matter here. Translating a name back into Django's positional
    ``o=<index>`` query param happens later, against a live ``ChangeList``'s
    own ``list_display`` — which, unlike ``get_list_display()``, has an
    ``action_checkbox`` column prepended whenever the model has any actions —
    not against this list.
    """

    def execute(self, model_admin: ModelAdmin, request: HttpRequest) -> list[str]:
        sortable = set(model_admin.get_sortable_by(request))
        return [name for name in model_admin.get_list_display(request) if name in sortable]
