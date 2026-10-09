from django.contrib.admin import ModelAdmin
from django.db.models import Model
from django.http import HttpRequest
from fastmcp.resources import ResourceContent, ResourceResult

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions.get_model_json_representation import (
    GetModelJsonRepresentation,
)
from django_unfold_agentic_layer.resources.actions.render_model_instance_markdown import (
    RenderModelInstanceMarkdown,
)
from django_unfold_agentic_layer.resources.schemas import AdminModelResource


class BuildListResourceResult(BaseLogicAction):
    """A resource's instances rendered as both JSON and Markdown (spec §8.1) —
    a single instance is just the ``len(instances) == 1`` case of this, not a
    separately-implemented path.
    """

    def execute(
        self,
        model_admin: ModelAdmin,
        request: HttpRequest,
        model_resource: AdminModelResource,
        instances: list[Model],
        total: int,
    ) -> ResourceResult:
        get_json = GetModelJsonRepresentation()
        render_markdown = RenderModelInstanceMarkdown()

        json_items = [get_json.execute(model_admin, request, obj) for obj in instances]
        # TODO: reconsider returning both JSON and Markdown for lists — it
        # doubles the response size.
        markdown = (
            "\n\n---\n\n".join(render_markdown.execute(item, model_resource) for item in json_items)
            or "*(no results)*"
        )

        return ResourceResult(
            contents=[
                ResourceContent(json_items, mime_type="application/json"),
                ResourceContent(markdown, mime_type="text/markdown"),
            ],
            meta={"total": total, "count": len(instances)},
        )
