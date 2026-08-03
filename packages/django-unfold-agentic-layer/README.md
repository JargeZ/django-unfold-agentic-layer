# django-unfold-agentic-layer

An installable Django app (`INSTALLED_APPS`) that turns your project into an MCP (Model Context Protocol) server for the [Django Unfold](https://unfoldadmin.com) admin theme — AI clients that speak MCP over Streamable HTTP get a documentation-aware endpoint with zero extra process to run.

## Install

```bash
pip install django-unfold-agentic-layer
```

```python
INSTALLED_APPS = [
    ...,
    "django_unfold_agentic_layer",
]
```

```python
# your project's root urls.py
urlpatterns = [
    path("", include("django_unfold_agentic_layer.urls")),
]
```

This wires up a single route: `POST /mcp/`.

Works under **either WSGI or ASGI** deployment — the bridge that delegates requests into the MCP server doesn't rely on ASGI-only mechanics (see `mcp_server/bridge.py` and CLAUDE.md for how).

## Access

`/mcp/` requires an authenticated, active staff user:

- Anonymous request → `401` JSON body
- Authenticated but non-staff → `403` JSON body
- Authenticated staff → delegated to the MCP server

Point any MCP client that speaks Streamable HTTP at `https://your-project.example/mcp/`, authenticated the same way the rest of your admin is (session cookie, or whatever auth your deployment fronts it with).

## What's available today

25 documentation tools covering Django Unfold installation, configuration, actions, filters, decorators, components, inlines, widgets, tabs, dashboards, custom pages, styles/scripts, and every documented third-party integration (import-export, guardian, simple-history, celery-beat, modeltranslation, money, constance, location-field, djangoql, json-widget), plus a full-text `unfold_search_docs` tool. See `mcp_server/tools.py` / `mcp_server/docs.py`.

This is a first pass: the endpoint doesn't yet expose anything that introspects or mutates *your* admin (models, registered actions, data) — see the roadmap note in the repository's `CLAUDE.md` for what's planned next.

## Settings

Configure the app with an `UNFOLD_AGENTIC_LAYER` dict in your project's settings — the same override-by-dict pattern Unfold itself uses for its own `UNFOLD` setting. Any key you omit falls back to its default. See `django_unfold_agentic_layer/conf.py` for the current list of settings; none are required for `/mcp/` to work.

## Development

```bash
uv sync
cd packages/django-unfold-agentic-layer
uv run pytest
```

`django_test_app/` is a throwaway Django project (not a template for a real project) that the test suite boots to exercise this package end-to-end, including a real HTTP round-trip against `/mcp/` (see `tests/test_mcp_endpoint.py`).

See the [repository README](https://github.com/JargeZ/django-unfold-agentic-layer#readme) and `CLAUDE.md` for the broader architecture.
