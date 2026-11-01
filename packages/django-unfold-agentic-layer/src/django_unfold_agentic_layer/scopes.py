"""OAuth scopes: what an MCP login may do, on top of its user's own permissions.

The user picks them on the consent page. ``mcp:read`` is always granted;
the other two are independent. A scope never widens a user's permissions —
it only narrows what the token can reach. Tools and resources outside the
token's scopes are not registered at all, and every handler re-checks its
scope on each call (``builders._shared.get_django_request``).
"""

from django.utils.translation import gettext_lazy as _

#: Detail and list resources.
READ = "mcp:read"
#: Create and update tools, and admin actions not marked ``DANGER``.
WRITE = "mcp:write"
#: Delete tools and ``DANGER`` admin actions.
DESTRUCTIVE = "mcp:destructive"

ALL = [READ, WRITE, DESTRUCTIVE]

#: Granted with every login: an agent that can't read can't act sensibly.
ALWAYS_GRANTED = {READ}

DESCRIPTIONS = {
    READ: _("See the records you can view in the admin"),
    WRITE: _("Create and change records, and run admin actions"),
    DESTRUCTIVE: _("Delete records and run actions marked as dangerous"),
}


def granted(requested: list[str] | None, chosen: list[str]) -> list[str]:
    """The scopes a login gets: what the user ``chosen`` on the consent page,
    within what the client ``requested`` (``None``: everything), plus
    :data:`ALWAYS_GRANTED`. In :data:`ALL` order."""
    allowed = set(ALL if requested is None else requested)
    picked = (set(chosen) & allowed) | ALWAYS_GRANTED
    return [scope for scope in ALL if scope in picked]
