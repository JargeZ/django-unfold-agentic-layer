"""Small helpers shared by the resource/tool builders in this package."""

import hashlib
import inspect
import logging
import uuid
from collections.abc import Callable
from typing import Annotated, Any, Literal, TypeVar

from asgiref.sync import sync_to_async
from django.core.cache import caches
from django.http import HttpRequest
from fastmcp import Context
from fastmcp.exceptions import FastMCPError, ToolError
from fastmcp.server.dependencies import get_http_request
from mcp.types import ElicitRequest, ElicitRequestFormParams, InputRequiredResult
from pydantic import AfterValidator, Field

from django_unfold_agentic_layer.conf import Settings, get_config
from django_unfold_agentic_layer.resources.schemas import EditableFieldInfo, FileUploadInput

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

#: A primary key as a tool argument: agents send ``1`` as often as ``"1"``,
#: so accept both and hand handlers a ``str`` either way.
PK = Annotated[str | int, AfterValidator(str)]

#: The ASGI scope key bridge.py stashes the originating Django HttpRequest
#: under (see mcp_server/bridge.py) — namespaced to avoid colliding with any
#: key the MCP SDK's own transport might use.
REQUEST_SCOPE_KEY = "django_unfold_agentic_layer.request"

#: Lifetime of a confirmation round's sealed ``requestState`` — also how long
#: an answered one is remembered as consumed (see :func:`is_confirmed`).
REQUEST_STATE_TTL = 600

_CONSUMED_STATE_CACHE_PREFIX = "django_unfold_agentic_layer.consumed_request_state:"


def _consumed_state_cache_key(request_state: str) -> str:
    # Hashed: a sealed requestState is longer than memcached's 250-char key limit.
    return _CONSUMED_STATE_CACHE_PREFIX + hashlib.sha256(request_state.encode()).hexdigest()


#: python_type -> the Python type an editable field's value is accepted as.
#: Deliberately coarse — Django's own form validation does the real parsing
#: (see EditableFieldInfo's docstring).
_BASE_TYPES: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "file": FileUploadInput,
}


def get_django_request() -> HttpRequest:
    """The live Django ``HttpRequest`` behind the current MCP call.

    Works because bridge.py hands the *same* scope dict all the way down to
    ``StreamableHTTPSessionManager``, which threads it through as
    ``RequestContext.request`` — see spec §6 for the full chain, verified
    end-to-end against a real HTTP POST through ``/mcp/``.
    """
    return get_http_request().scope[REQUEST_SCOPE_KEY]


async def run_in_django(
    label: str, fn: Callable[..., _T], *args: Any, error: type[FastMCPError] = ToolError
) -> _T:
    """Run the Django-touching ``fn(*args)`` on Django's thread-sensitive
    worker (see CLAUDE.md for why not fastmcp's own offload), and turn any
    exception into ``error`` *there*, still in sync context.

    fastmcp formats an escaping exception (``f"{e}"``) on the event loop. A
    message that lazily touches the ORM — e.g. a ``ProtectedError`` listing
    instances whose ``__str__`` follows a FK — then trips
    ``SynchronousOnlyOperation`` inside fastmcp's error handler, and the
    client gets a bare 500 instead of the error. ``from None`` drops the
    chain for the same reason: fastmcp logs it on the event loop too.
    """

    def guarded() -> _T:
        try:
            return fn(*args)
        except FastMCPError:
            raise
        except Exception as e:
            logger.exception("Error in %s", label)
            raise error(f"{type(e).__name__} in {label}: {e}") from None

    return await sync_to_async(guarded, thread_sensitive=True)()


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
    if field.python_type in ("related", "multi_related"):
        # Resources render relations as dj-admin:// URIs; accept them back.
        related_pk = Annotated[str | int, AfterValidator(_uri_to_pk(field.related_resource_uri))]
        base_type = list[related_pk] if field.python_type == "multi_related" else related_pk
    elif field.python_type == "choice":
        base_type = _choice_literal(field)
    else:
        base_type = _BASE_TYPES[field.python_type]

    description = field.title if not field.help_text else f"{field.title} — {field.help_text}"
    if field.required:
        description = f"{description} (required)"
    if field.related_resource_uri:
        description = (
            f"{description}. Pass a pk or its {field.related_resource_uri}{{pk}}/ URI; "
            f"browse valid values at {field.related_resource_uri}"
        )

    return inspect.Parameter(
        field.name,
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=None,
        annotation=Annotated[base_type | None, Field(description=description)],
    )


def _uri_to_pk(prefix: str) -> Callable[[str | int], str]:
    """``dj-admin://app/model/187/`` -> ``"187"``. A URI of another model is
    left as-is, so the form rejects it with its own ``invalid_choice``."""

    def to_pk(value: str | int) -> str:
        value = str(value)
        return value.removeprefix(prefix).rstrip("/") if value.startswith(prefix) else value

    return to_pk


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
    # Django's default LocMemCache is per-process; multi-worker deployments
    # need a shared backend here (CONFIRMATION_CACHE) for replay protection.
    cache = caches[get_config()[Settings.CONFIRMATION_CACHE]]
    if not cache.add(_consumed_state_cache_key(ctx.request_state), True, timeout=REQUEST_STATE_TTL):
        return None
    confirm = ctx.input_responses.get("confirm")
    return (
        confirm is not None
        and confirm.action == "accept"
        and (confirm.content or {}).get("confirmed") is not False
    )
