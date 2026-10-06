from typing import Any

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.schemas import AdminModelResource


class RenderModelInstanceMarkdown(BaseLogicAction):
    """A human-skimmable Markdown rendering of one instance's JSON
    representation — a flat field list under a verbose-name heading.

    Deliberately minimal for this iteration: a single fixed field/type-agnostic
    layout, not the extensible field-type/widget renderer registry sketched in
    spec §8.3 (a real per-type registry is only worth building once there's a
    second consumer that needs it).
    """

    def execute(self, value: dict[str, Any], model_resource: AdminModelResource) -> str:
        lines = [f"# {model_resource.verbose_name} #{value.get('pk')}", ""]
        lines.extend(
            f"- **{key}**: {self._format(val)}" for key, val in value.items() if key != "pk"
        )
        return "\n".join(lines)

    def _format(self, value: Any) -> str:
        if value is None:
            return "*(empty)*"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value) if value else "*(empty)*"
        return str(value)
