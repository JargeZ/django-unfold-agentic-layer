"""The one place an exception becomes text an agent sees.

Known failures get a clear message; anything else gets an opaque reference
the operator can find in the ``tools`` log. Nothing else of an unexpected
exception (database errors carry SQL and values) reaches the client.
"""

import uuid
from itertools import islice

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db.models import ProtectedError, RestrictedError

from django_unfold_agentic_layer import log

_MAX_LISTED_BLOCKERS = 10


class AgentError(Exception):
    """A failure whose message is written for the agent: raise it with text
    that says what went wrong and what to do instead."""


def format_error(exc: Exception, label: str) -> str:
    """The agent-facing message for ``exc`` raised while running ``label``.

    Must be called in sync context: a ``ProtectedError``'s objects may
    follow a foreign key in their ``__str__``.
    """
    message = _known_message(exc)
    if message is not None:
        log.tools.info("Refused %s: %s", label, message)
        return message
    ref = uuid.uuid4().hex[:8]
    log.tools.exception("Error in %s (ref %s)", label, ref)
    return f"Internal error in {label} (ref {ref}). The server log has the details."


def _known_message(exc: Exception) -> str | None:
    if isinstance(exc, AgentError):
        return str(exc)
    if isinstance(exc, PermissionDenied):
        return str(exc) or "You do not have permission to do this."
    if isinstance(exc, ObjectDoesNotExist):
        return "Not found."
    if isinstance(exc, ValidationError):
        return " ".join(exc.messages)
    if isinstance(exc, ProtectedError | RestrictedError):
        return f"Still referenced by {describe_blockers(exc)}. Delete or reassign those first."
    return None


def describe_blockers(exc: ProtectedError | RestrictedError) -> str:
    """The objects that stop a deletion, the first few by name."""
    blockers = getattr(exc, "protected_objects", None) or exc.restricted_objects
    listed = ", ".join(
        f"{obj._meta.verbose_name} {obj} (pk={obj.pk})"
        for obj in islice(blockers, _MAX_LISTED_BLOCKERS)
    )
    if len(blockers) > _MAX_LISTED_BLOCKERS:
        listed = f"{listed} and {len(blockers) - _MAX_LISTED_BLOCKERS} more"
    return listed
