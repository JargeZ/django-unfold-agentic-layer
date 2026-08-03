from django.contrib.admin import ModelAdmin

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions._shared import (
    get_base_unfold_actions,
    unfold_action_to_info,
)
from django_unfold_agentic_layer.resources.schemas import ActionInfo


class ExtractAppLevelActions(BaseLogicAction):
    """django-unfold's ``actions_list`` — the changelist-top actions that act
    on the model as a whole, without selecting or opening any instance.

    See https://unfoldadmin.com/docs/actions/changelist/. Returns ``[]`` for
    a plain ``ModelAdmin`` that isn't django-unfold's.
    """

    def execute(self, model_admin: ModelAdmin) -> list[ActionInfo]:
        return [
            unfold_action_to_info(action)
            for action in get_base_unfold_actions(model_admin, "_get_base_actions_list")
        ]
