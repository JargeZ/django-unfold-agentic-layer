from django.contrib.admin import ModelAdmin
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
    """

    def execute(
        self, model_admin: ModelAdmin, request: HttpRequest, limit: int, offset: int
    ) -> tuple[list[Model], int]:
        cl = model_admin.get_changelist_instance(request)
        instances = list(cl.queryset[offset : offset + limit])
        return instances, cl.result_count
