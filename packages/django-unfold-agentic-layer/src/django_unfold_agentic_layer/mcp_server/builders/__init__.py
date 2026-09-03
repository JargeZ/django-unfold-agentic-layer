"""Registers dynamic MCP resources/tools for admin-registered models on a
:class:`fastmcp.FastMCP` instance.

Per the normalization-layer invariant (spec §0.1), everything here consumes
:mod:`django_unfold_agentic_layer.resources.schemas` — it decides the *shape*
of each MCP primitive, never touching ``ModelAdmin``/``AdminSite`` directly.
The handler *bodies* these builders construct are the exception: at
invocation time they call the request-scoped execution actions in
``resources/actions/`` (``RunAdminChangelistQuery``, ``ApplyMCPFiltersToRequest``,
etc.), which *do* touch Django — that's normal query-time work, not schema
construction.
"""
