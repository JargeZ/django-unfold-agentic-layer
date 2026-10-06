from typing import Any

from django.contrib.admin import ModelAdmin
from django.http import HttpRequest
from unfold.enums import ActionVariant
from unfold.forms import BaseDialogForm

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions._shared import (
    django_action_to_info,
    get_filtered_unfold_actions,
)
from django_unfold_agentic_layer.resources.actions.extract_form_fields import ExtractFormFields
from django_unfold_agentic_layer.resources.schemas import ActionToolInfo, EditableFieldInfo

#: Django's built-in bulk delete only renders a confirmation page unless
#: re-POSTed with ``post=yes``; ``delete_*`` tools already cover deletion,
#: with their own confirmation step.
_SKIPPED_BULK_ACTIONS = {"delete_selected"}

#: ``action_form`` plumbing, not user input: the chosen action is the tool
#: itself, and "select across" is the explicit ``pks`` list.
_ACTION_FORM_PLUMBING = {"action", "select_across"}

_SCOPE_HINTS = {
    "bulk": "Runs on the selected {plural} (pass their pks).",
    "model": "Runs on {plural} as a whole, without selecting any.",
    "instance": "Runs on one {name} (pass its pk).",
}


class ExtractActionTools(BaseLogicAction):
    """Every admin action the requesting user could trigger, described as a
    tool: Django's bulk ``actions`` and Unfold's ``actions_list``,
    ``actions_row`` and ``actions_detail`` (dropdown groups are already
    flattened by Unfold's own getters). All sources are the same
    permission-filtered calls the admin itself renders from.

    **Not covered: ``actions_submit_line``.** Those run inside
    ``ModelAdmin.save_model()`` when a changeform is saved with the action's
    button, so they aren't standalone calls. Two ways to support them later:

    1. optional ``bool`` flags on the ``update_*`` tool, which put the
       action's ``action_name`` into the synthesized ``request.POST`` so
       Unfold's own ``save_model()`` runs it — closest to the browser;
    2. a separate ``run_*(pk, …form fields)`` tool that saves the instance
       through the change form and triggers the action — more discoverable,
       but duplicates the update tool.
    """

    def execute(self, model_admin: ModelAdmin, request: HttpRequest) -> list[ActionToolInfo]:
        tools: dict[str, ActionToolInfo] = {}
        for tool in [
            *self._bulk_actions(model_admin, request),
            *self._unfold_actions(model_admin, request, "get_actions_list", "model"),
            *self._unfold_actions(model_admin, request, "get_actions_row", "instance"),
            *self._unfold_actions(model_admin, request, "get_actions_detail", "instance"),
        ]:
            # A method listed in both actions_row and actions_detail is one
            # action with one signature — register it once.
            tools.setdefault(tool.tool_name, tool)
        return list(tools.values())

    def _bulk_actions(self, model_admin: ModelAdmin, request: HttpRequest) -> list[ActionToolInfo]:
        form_fields = [
            field
            for field in ExtractFormFields().execute(model_admin.action_form().fields)
            if field.name not in _ACTION_FORM_PLUMBING
        ]
        return [
            self._tool(
                model_admin,
                name=key,
                title=django_action_to_info(model_admin, resolved).title,
                scope="bulk",
                fields=form_fields,
                variant=getattr(resolved[0], "variant", None),
            )
            for key, resolved in model_admin.get_actions(request).items()
            if key not in _SKIPPED_BULK_ACTIONS
        ]

    def _unfold_actions(
        self, model_admin: ModelAdmin, request: HttpRequest, getter_name: str, scope: str
    ) -> list[ActionToolInfo]:
        opts = model_admin.model._meta
        tools = []
        for action in get_filtered_unfold_actions(model_admin, request, getter_name):
            dialog = action.dialog or {}
            fields: list[EditableFieldInfo] = []
            if action.dialog is not None:
                form_class = dialog.get("form_class") or BaseDialogForm
                # An instance, not base_fields: dialog forms often build their
                # fields in __init__ from the request.
                form = form_class(request=request, object_id=None)
                fields = ExtractFormFields().execute(form.fields)
            tools.append(
                self._tool(
                    model_admin,
                    name=action.action_name.removeprefix(f"{opts.app_label}_{opts.model_name}_"),
                    title=str(action.description),
                    scope=scope,
                    fields=fields,
                    variant=action.variant,
                    dialog_text=[dialog.get("title"), dialog.get("description")],
                )
            )
        return tools

    def _tool(
        self,
        model_admin: ModelAdmin,
        *,
        name: str,
        title: str,
        scope: str,
        fields: list[EditableFieldInfo],
        variant: Any,
        dialog_text: list[Any] | None = None,
    ) -> ActionToolInfo:
        opts = model_admin.model._meta
        dangerous = variant == ActionVariant.DANGER
        hint = _SCOPE_HINTS[scope].format(name=opts.verbose_name, plural=opts.verbose_name_plural)
        texts = [title, *(str(text) for text in dialog_text or [] if text and str(text) != title)]
        parts = [f"{text.rstrip('.')}." for text in texts] + [hint]
        if dangerous:
            parts.append("Asks for confirmation before running.")
        return ActionToolInfo(
            tool_name=f"run_{opts.app_label}_{opts.model_name}_{name}",
            name=name,
            title=title,
            description=" ".join(parts),
            scope=scope,
            fields=fields,
            dangerous=dangerous,
        )
