from typing import Any

from django.contrib.admin import ModelAdmin, SimpleListFilter
from django.contrib.admin.views.main import ChangeList
from django.db.models import Model
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction


class RunAdminChangelistQuery(BaseLogicAction):
    """Runs ``request``'s filters/search/ordering through the model's own
    ``ChangeList`` (so search, ``list_filter``, and ``o=`` behave exactly as
    they would in the browser — see spec §4/§5), then applies *our own*
    ``limit``/``offset`` slice in Python.

    Deliberately does not rely on ``ChangeList.get_results()``'s own
    pagination: that's driven by Django's ``p=``/``list_per_page``, which
    has no ``offset`` equivalent (spec §5.2) — ``cl.queryset`` (the filtered,
    ordered, *unsliced* queryset ``ChangeList.__init__`` already built) is the
    thing to slice instead. ``cl.result_count`` is reused for the total count
    rather than issuing a second ``COUNT(*)``, since ``get_results()`` already
    ran during ``get_changelist_instance()``.

    ``order_by`` is only applied here for ``pk``/``-pk``, which has no ``o=``
    column index (see ``ApplyMCPFiltersToRequest``).
    """

    def execute(
        self,
        model_admin: ModelAdmin,
        request: HttpRequest,
        limit: int,
        offset: int,
        order_by: str | None = None,
    ) -> tuple[list[Model], int]:
        cl = model_admin.get_changelist_instance(request)
        self._check_filters_applied(cl, request)
        queryset = cl.queryset
        if order_by and order_by.removeprefix("-") == "pk":
            queryset = queryset.order_by(order_by)
        instances = list(queryset[offset : offset + limit])
        return instances, cl.result_count

    def _check_filters_applied(self, cl: ChangeList, request: HttpRequest) -> None:
        """Raise when a filter got a value but did not filter by it.

        A ``ChangeList`` treats a spec's ``queryset()`` returning ``None`` as
        "no filter", so an invalid value (Unfold's ``RangeDateFilter`` on
        ``date_from=not-a-date``) is silently dropped; some specs also ignore
        a parameter they declare (Unfold's ``RelatedDropdownFilter`` and its
        ``__isnull``). The browser hides this; an agent would trust the result.
        Probed against an empty queryset, so no extra database query runs.
        """
        base = cl.root_queryset.none()
        for spec in cl.filter_specs:
            provided = {
                param: request.GET[param]
                for param in spec.expected_parameters()
                if param and request.GET.get(param)
            }
            if not provided:
                continue
            result = spec.queryset(request, base)
            if isinstance(spec, SimpleListFilter):
                # Declared lookups are the contract: a declared value may
                # legitimately leave the queryset unchanged (e.g. "all").
                allowed = [str(value) for value, _label in spec.lookup_choices]
                if allowed and spec.value() not in allowed:
                    self._raise(provided, f"Allowed values: {', '.join(allowed)}.")
                if result is None and not allowed:
                    self._raise(provided)
            # ponytail: a field filter whose value legitimately changes nothing
            # is reported too; add an allowlist setting if one turns up.
            elif result is None or result is base:
                self._raise(provided)

    def _raise(self, provided: dict[str, Any], hint: str = "") -> None:
        params = ", ".join(f"{param}={value!r}" for param, value in provided.items())
        raise ValueError(
            f"Filter ignored {params}: the value is invalid or not supported. {hint}".strip()
        )
