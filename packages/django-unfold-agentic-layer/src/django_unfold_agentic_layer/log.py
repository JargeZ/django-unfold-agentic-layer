"""The library's loggers, named by what they report rather than by module.

All are children of ``django_unfold_agentic_layer``, so a host project
configures the whole library with one ``LOGGING["loggers"]`` entry, or one
area at a time by its full name.
"""

import logging

ROOT = "django_unfold_agentic_layer"

#: The ``/mcp`` endpoint: rejected calls, dev-mode warnings; bodies at DEBUG.
mcp = logging.getLogger(f"{ROOT}.mcp")
#: The OAuth flow: discovery, login, consent, token lifecycle.
oauth = logging.getLogger(f"{ROOT}.oauth")
#: Tool and resource handlers: errors raised while running them.
tools = logging.getLogger(f"{ROOT}.tools")
#: Building the per-user MCP server from the admin registry.
builder = logging.getLogger(f"{ROOT}.builder")
