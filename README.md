<p align="center">
  <img src="https://img.shields.io/pypi/v/django-unfold-agentic-layer?color=6366f1&style=for-the-badge" alt="PyPI version" />
  <img src="https://img.shields.io/pypi/pyversions/django-unfold-agentic-layer?color=818cf8&style=for-the-badge" alt="Python versions" />
  <img src="https://img.shields.io/badge/MCP-Compatible-4f46e5?style=for-the-badge" alt="MCP Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-059669?style=for-the-badge" alt="License" />
</p>

# 🔮 Django Unfold Agentic Layer

> **An installable Django app that turns your project into an MCP server for the [Django Unfold](https://unfoldadmin.com) admin theme.**

Install it, add it to `INSTALLED_APPS`, include its `urls.py` — your project now serves an MCP (Model Context Protocol) endpoint at `/mcp/` that AI agents can talk to over Streamable HTTP. No separate process, no extra deployment step.

This repository is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/); `django-unfold-agentic-layer` (in `packages/django-unfold-agentic-layer/`) is currently its only member. See [`packages/django-unfold-agentic-layer/README.md`](packages/django-unfold-agentic-layer/README.md) for install/usage instructions, and [CLAUDE.md](CLAUDE.md) for architecture and conventions.

## Quick start

```bash
pip install django-unfold-agentic-layer
```

```python
# settings.py
INSTALLED_APPS = [
    "unfold",                        # before django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_unfold_agentic_layer",
]
```

```python
# urls.py (project root)
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("django_unfold_agentic_layer.urls")),  # → POST /mcp/
]
```

Full details (middleware, URL prefix, editable/path install, access rules) in the [package README](packages/django-unfold-agentic-layer/README.md#install).

---

## Why this exists

AI coding agents frequently hallucinate when generating Django Unfold code — inventing non-existent settings, wrong import paths, or missing `INSTALLED_APPS` ordering requirements. `/mcp/` currently exposes 25 documentation tools sourced directly from the official Django Unfold docs, so an agent can look up the real answer instead of guessing. A follow-up phase adds tools that introspect and act on *your* admin (registered models, actions, data) — see the roadmap note in `CLAUDE.md`.

## How it works

`FastMCP` (the [`fastmcp`](https://gofastmcp.com) package) owns tool registration and the MCP protocol itself; a small Django view (`django_unfold_agentic_layer.mcp_server.bridge`) delegates each `/mcp/` request into it directly — no ASGI-level route mounting required in your project, and no dependency on your project running under ASGI specifically. See `packages/django-unfold-agentic-layer/README.md` and `CLAUDE.md` for the technical detail.

## Development

```bash
uv sync                                          # from repo root
cd packages/django-unfold-agentic-layer
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE) for details.
