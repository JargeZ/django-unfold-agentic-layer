"""Small helpers shared by the resource/tool builders in this package."""

import inspect
import uuid
from typing import Annotated, Literal

from django.core.cache import cache
from django.http import HttpRequest
from fastmcp import Context
from fastmcp.server.dependencies import get_http_request
from mcp.types import ElicitRequest, ElicitRequestFormParams, InputRequiredResult
from pydantic import Field

from django_unfold_agentic_layer.resources.schemas import EditableFieldInfo

#: The ASGI scope key bridge.py stashes the originating Django HttpRequest
#: under (see mcp_server/bridge.py) — namespaced to avoid colliding with any
#: key the MCP SDK's own transport might use.
REQUEST_SCOPE_KEY = "django_unfold_agentic_layer.request"

#: Lifetime of a confirmation round's sealed ``requestState`` — also how long
#: an answered one is remembered as consumed (see :func:`is_confirmed`).
REQUEST_STATE_TTL = 600

_CONSUMED_STATE_CACHE_PREFIX = "django_unfold_agentic_layer.consumed_request_state:"

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


def confirmation_request(message: str, title: str, request_state: str) -> InputRequiredResult:
    """Ask the client to confirm before a destructive tool runs.

    Goes through the modern-protocol ``InputRequiredResult`` (SEP-2322), not
    ``ctx.elicit()``: the latter suspends the tool call mid-flight waiting on
    a server-initiated request the client answers over the *same*
    connection, which stateless mode's single-shot POST has no channel for
    (see bridge.py's session manager). ``InputRequiredResult`` instead
    *returns* a description of the needed input and lets the client
    re-invoke the tool with the answer. Pair with :func:`is_confirmed`.

    ``request_state`` gets a random nonce appended, so every round is unique
    and :func:`is_confirmed` can accept each answer only once.
    """
    return InputRequiredResult(
        result_type="input_required",
        input_requests={
            "confirm": ElicitRequest(
                method="elicitation/create",
                params=ElicitRequestFormParams(
                    message=message,
                    requestedSchema={
                        "type": "object",
                        # A default lets form-rendering clients (Claude Code)
                        # submit an untouched checkbox; without one they treat
                        # the required field as unfilled and silently refuse
                        # to submit on "accept".
                        "properties": {
                            "confirmed": {"type": "boolean", "title": title, "default": True}
                        },
                    },
                ),
            )
        },
        request_state=f"{request_state}:{uuid.uuid4().hex}",
    )


def is_confirmed(ctx: Context) -> bool | None:
    """``None`` before :func:`confirmation_request` was answered, else whether
    the user accepted. decline/cancel (or a missing answer) carry no
    ``content``; an accept counts unless ``confirmed`` was explicitly unticked.

    An answer only counts when it echoes the ``requestState`` this server
    minted (sealed, so unforgeable) and only the first time: otherwise a
    client could skip the prompt by sending ``inputResponses`` straight away,
    or replay one confirmation into many runs. Either way it's asked again.
    """
    if ctx.input_responses is None or ctx.request_state is None:
        return None
    # ponytail: Django's default LocMemCache is per-process; multi-worker
    # deployments need a shared CACHES backend for replay protection to hold.
    if not cache.add(
        _CONSUMED_STATE_CACHE_PREFIX + ctx.request_state, True, timeout=REQUEST_STATE_TTL
    ):
        return None
    confirm = ctx.input_responses.get("confirm")
    return (
        confirm is not None
        and confirm.action == "accept"
        and (confirm.content or {}).get("confirmed") is not False
    )
