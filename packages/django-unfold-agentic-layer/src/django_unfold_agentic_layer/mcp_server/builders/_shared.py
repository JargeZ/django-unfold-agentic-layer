"""Small helpers shared by the resource/tool builders in this package."""

import inspect
from typing import Annotated, Literal

from django.http import HttpRequest
from fastmcp.server.dependencies import get_http_request
from pydantic import Field

from django_unfold_agentic_layer.resources.schemas import EditableFieldInfo

#: The ASGI scope key bridge.py stashes the originating Django HttpRequest
#: under (see mcp_server/bridge.py) — namespaced to avoid colliding with any
#: key the MCP SDK's own transport might use.
REQUEST_SCOPE_KEY = "django_unfold_agentic_layer.request"

#: python_type -> the Python type an editable field's value is accepted as.
#: Deliberately coarse — Django's own form validation does the real parsing
#: (see EditableFieldInfo's docstring).
_BASE_TYPES: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "related": str,
    "multi_related": list[str],
}


def get_django_request() -> HttpRequest:
    """The live Django ``HttpRequest`` behind the current MCP call.

    Works because bridge.py hands the *same* scope dict all the way down to
    ``StreamableHTTPSessionManager``, which threads it through as
    ``RequestContext.request`` — see spec §6 for the full chain, verified
    end-to-end against a real HTTP POST through ``/mcp/``.
    """
    return get_http_request().scope[REQUEST_SCOPE_KEY]


def build_editable_field_parameter(field: EditableFieldInfo) -> inspect.Parameter:
    """One ``inspect.Parameter`` for a create/update tool's dynamic signature.

    Always optional at the tool-parameter level — even for a field the model
    requires — so create and update share one, uniform, Django-form-validated
    error path: if a required field were instead a required *tool* parameter,
    fastmcp/pydantic would reject an omitted call before it ever reached
    ``CreateModelInstance``/``UpdateModelInstance``, with a raw pydantic error
    instead of the same structured ``{"success": False, "errors": {...}}``
    shape every other validation failure gets. ``field.required`` still shows
    up in the description text so an agent knows to provide it anyway. For
    update this doubling as partial-update semantics (spec §9) is also
    exactly what's wanted: an agent only sends the fields it wants to change,
    and ``UpdateModelInstance`` merges the rest in from the current instance
    before validating.
    """
    base_type = (
        _choice_literal(field) if field.python_type == "choice" else _BASE_TYPES[field.python_type]
    )

    description = field.title if not field.help_text else f"{field.title} — {field.help_text}"
    if field.required:
        description = f"{description} (required)"
    if field.related_resource_uri:
        description = f"{description}. Browse valid values at {field.related_resource_uri}"

    return inspect.Parameter(
        field.name,
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=None,
        annotation=Annotated[base_type | None, Field(description=description)],
    )


def _choice_literal(field: EditableFieldInfo) -> type:
    values = [value for value, _label in (field.choices or []) if value]
    return Literal[tuple(values)] if values else str
