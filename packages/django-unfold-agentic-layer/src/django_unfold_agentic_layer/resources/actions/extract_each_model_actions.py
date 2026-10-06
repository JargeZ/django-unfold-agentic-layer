from django.contrib.admin import ModelAdmin
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions._shared import (
    django_action_to_info,
    get_filtered_unfold_actions,
    unfold_action_to_info,
)
from django_unfold_agentic_layer.resources.schemas import ActionInfo


class ExtractEachModelActions(BaseLogicAction):
    """Actions that act on one or more *instances* of the model: Django's
    bulk ``actions`` (this ``ModelAdmin``'s own, plus any registered
    site-wide, e.g. the default "delete selected"), and — for a
    django-unfold ``ModelAdmin`` — its row, detail, and submit-line actions.

    Unlike ``actions_list`` (see :class:`ExtractAppLevelActions`), none of
    these can run without a selected or open instance. Both sources are
    already permission-filtered by Django/unfold themselves
    (``get_actions``/``get_actions_row``/etc.), so a user only sees what they
    could actually invoke.
    """

    def execute(self, model_admin: ModelAdmin, request: HttpRequest) -> list[ActionInfo]:
        return [
            *self._django_bulk_actions(model_admin, request),
            *(
                unfold_action_to_info(action)
                for getter_name in (
                    "get_actions_row",
                    "get_actions_detail",
                    "get_actions_submit_line",
                )
                for action in get_filtered_unfold_actions(model_admin, request, getter_name)
            ),
        ]

    def _django_bulk_actions(
        self, model_admin: ModelAdmin, request: HttpRequest
    ) -> list[ActionInfo]:
        return [
            django_action_to_info(model_admin, resolved)
            for resolved in model_admin.get_actions(request).values()
        ]
