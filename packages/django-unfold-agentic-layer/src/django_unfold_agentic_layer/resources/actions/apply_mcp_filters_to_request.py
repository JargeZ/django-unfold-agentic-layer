import copy
from typing import Any
from urllib.parse import urlencode

from django.contrib.admin import ModelAdmin
from django.http import HttpRequest, QueryDict

from django_unfold_agentic_layer.actions.base import BaseLogicAction


class ApplyMCPFiltersToRequest(BaseLogicAction):
    """Builds a *copy* of ``request`` with its ``GET`` populated from MCP tool
    params, translating our own ``order_by`` into Django's ``o=<index>``
    changelist dialect (see spec §5.1) — filter/search params pass through
    verbatim, since their names already *are* the real GET parameter names
    (§3.2). ``limit``/``offset`` are not Django concepts and are handled by
    the caller as a plain queryset slice, not translated here.

    Returns a copy so the original request (and its ``.GET``, used elsewhere
    e.g. for permission checks) is never mutated.
    """

    def execute(
        self, request: HttpRequest, model_admin: ModelAdmin, params: dict[str, Any]
    ) -> HttpRequest:
        params = dict(params)
        order_by = params.pop("order_by", None)
        params.pop("limit", None)
        params.pop("offset", None)

        get_params = {key: value for key, value in params.items() if value is not None}
        # pk isn't a list_display column, so it has no o= index;
        # RunAdminChangelistQuery orders by it directly.
        if order_by and order_by.removeprefix("-") != "pk":
            get_params["o"] = self._translate_order_by(model_admin, request, order_by)

        new_request = copy.copy(request)
        new_request.GET = QueryDict(urlencode(get_params))
        return new_request

    def _translate_order_by(
        self, model_admin: ModelAdmin, request: HttpRequest, order_by: str
    ) -> str:
        # Mirrors ModelAdmin.get_changelist_instance()'s own list_display
        # construction (options.py) rather than building a throwaway
        # ChangeList just to read its .list_display: the "o=" query param is
        # a positional index into *this* sequence, including the
        # action_checkbox column get_changelist_instance() prepends whenever
        # the model has any actions — get_list_display() alone omits it and
        # would silently produce an off-by-one index.
        list_display = list(model_admin.get_list_display(request))
        if model_admin.get_actions(request):
            list_display = ["action_checkbox", *list_display]

        descending = order_by.startswith("-")
        field_name = order_by.removeprefix("-")
        index = list_display.index(field_name)
        return f"-{index}" if descending else str(index)
