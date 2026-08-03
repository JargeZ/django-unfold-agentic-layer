from django.contrib.admin import ModelAdmin

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions._shared import (
    django_action_to_info,
    get_base_unfold_actions,
    unfold_action_to_info,
)
from django_unfold_agentic_layer.resources.schemas import ActionInfo


class ExtractEachModelActions(BaseLogicAction):
    """Actions that act on one or more *instances* of the model: Django's
    bulk ``actions`` (this ``ModelAdmin``'s own, plus any registered
    site-wide, e.g. the default "delete selected"), and — for a
    django-unfold ``ModelAdmin`` — its row, detail, and submit-line actions.

    Unlike ``actions_list`` (see :class:`ExtractAppLevelActions`), none of
    these can run without a selected or open instance.
    """

    def execute(self, model_admin: ModelAdmin) -> list[ActionInfo]:
        return [
            *self._django_bulk_actions(model_admin),
            *(
                unfold_action_to_info(action)
                for getter_name in (
                    "_get_base_actions_row",
                    "_get_base_actions_detail",
                    "_get_base_actions_submit_line",
                )
                for action in get_base_unfold_actions(model_admin, getter_name)
            ),
        ]

    def _django_bulk_actions(self, model_admin: ModelAdmin) -> list[ActionInfo]:
        action_names = (
            *(model_admin.actions or []),
            *(name for name, _func in model_admin.admin_site.actions),
        )

        infos = []
        seen_keys: set[str] = set()
        for action in action_names:
            resolved = model_admin.get_action(action)
            if resolved is None or resolved[1] in seen_keys:
                continue
            seen_keys.add(resolved[1])
            infos.append(django_action_to_info(model_admin, resolved))
        return infos
