# django-unfold-agentic-layer

An installable Django app (`INSTALLED_APPS`) that turns your project into an MCP (Model Context Protocol) server for the [Django Unfold](https://unfoldadmin.com) admin theme — AI clients that speak MCP over Streamable HTTP get a documentation-aware endpoint with zero extra process to run.

## Install

```bash
pip install django-unfold-agentic-layer
```

For local development against a checkout, install it editable by path — e.g. with Poetry:

```toml
# [tool.poetry.dependencies]
django-unfold-agentic-layer = { path = "../django-unfold-agentic-layer/packages/django-unfold-agentic-layer", develop = true }
```

(point at `packages/django-unfold-agentic-layer/`, not the repo root — the root is a uv workspace with no `[project]` table.)

### `settings.py`

```python
INSTALLED_APPS = [
    # Unfold must come before django.contrib.admin.
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",  # required: /mcp/ authenticates staff users
    "django.contrib.contenttypes",
    "django.contrib.sessions",  # required for the admin login in the OAuth flow
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # ...
    "django_unfold_agentic_layer",  # exactly this string — it's both AppConfig.name and .label
    # your own apps
]

MIDDLEWARE = [
    # ...
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # ...
]
```

### `urls.py` (project root)

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("django_unfold_agentic_layer.urls")),  # → /mcp/, /mcp/o/…
]
```

Then `python manage.py migrate` (the app stores OAuth clients and hashed tokens in its own tables).

This wires up `POST /mcp` (URL name `django_unfold_agentic_layer:mcp`; `/mcp/` works too) plus its OAuth endpoints under `/mcp/o/` — every route the app adds lives under `mcp/`, so it can't collide with your own (e.g. a django-oauth-toolkit at `/o/`). To serve it under a prefix, change the include path — e.g. `path("agent/", include("django_unfold_agentic_layer.urls"))` gives `/agent/mcp`. The view is CSRF-exempt, so no extra CSRF setup is needed for MCP clients.

Works under **either WSGI or ASGI** deployment — the bridge that delegates requests into the MCP server doesn't rely on ASGI-only mechanics (see `mcp_server/bridge.py` and CLAUDE.md for how).

## Access

`/mcp/` speaks the standard [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) flow (OAuth 2.1 + PKCE, dynamic client registration), so clients log in on their own:

```bash
claude mcp add --transport http unfold https://your-project.example/mcp
# then /mcp → Authenticate: the browser opens your admin login, then a consent page
```

- No/invalid/expired `Bearer` token → `401` with `WWW-Authenticate: Bearer resource_metadata="…/mcp/o/.well-known/oauth-protected-resource"` — what clients use to start the login.
- Only active **staff** users can log in and approve a client; `is_active`/`is_staff` is re-checked on every request (`403` otherwise), so un-staffing someone cuts off their tokens immediately.
- A login lasts `SESSION_TTL` (default 1 day); no refresh tokens are issued, so the client re-runs the browser login after that.
- The Django session cookie does **not** authenticate `/mcp/` — only the token does.

The OAuth server itself is the MCP SDK's (`mcp.server.auth`); this app only stores its state. Discovery stays inside `/mcp/o/` (via the 401's `resource_metadata` and `<issuer>/.well-known/openid-configuration`), nothing is added at your site root. The issuer must be `https` (or `localhost`) — behind a proxy, set `SECURE_PROXY_SSL_HEADER`/`USE_X_FORWARDED_HOST` so Django builds the right absolute URLs.

## What's available today

**Documentation**: 25 tools covering Django Unfold installation, configuration, actions, filters, decorators, components, inlines, widgets, tabs, dashboards, custom pages, styles/scripts, and every documented third-party integration (import-export, guardian, simple-history, celery-beat, modeltranslation, money, constance, location-field, djangoql, json-widget), plus a full-text `unfold_search_docs` tool. See `mcp_server/tools.py` / `mcp_server/docs.py`.

**Your admin, live**: every model registered in `django.contrib.admin.site` that the authenticated user has permission on is exposed dynamically, mirroring what that user would see in the browser:

- A `dj-admin://{app_label}/{model_name}/{pk}/` resource per model — one instance's fields, rendered as both JSON and Markdown. Foreign keys/M2M come back as resource URIs to follow, not inlined objects.
- A `dj-admin://{app_label}/{model_name}/{?params}` resource per model for lists — the model's real `list_filter`/search GET parameters (verbatim, e.g. `author__id__exact`), plus `limit`/`offset`/`order_by`.
- `create_{app_label}_{model_name}` / `update_{app_label}_{model_name}` tools, backed by the model's own admin form — Django's `form.is_valid()` does the validation, errors come back structured per field.
- A `delete_{app_label}_{model_name}` tool that asks for confirmation (via the MCP "input required" round-trip) before deleting.
- A `run_{app_label}_{model_name}_{action}` tool per admin action — Django bulk `actions` (take `pks`), Unfold `actions_list` (whole model), `actions_row`/`actions_detail` (take `pk`). The action's form becomes the tool's parameters: an Unfold `dialog` `form_class`, or for bulk actions your `ModelAdmin.action_form` extras. Results report the action's messages, its redirect, and any returned file (e.g. a CSV export) inline. Actions with `variant=ActionVariant.DANGER` ask for confirmation first.

Everything above is permission-filtered per request using Django's/Unfold's own permission checks (`has_*_permission`, `get_actions`, …) — a user only ever sees resources and tools for what they could actually do in the admin.

Not yet covered: `actions_submit_line` actions (they run while saving a changeform), Django's built-in bulk `delete_selected` (use the delete tool), and there's no stateful/SSE mode for server-initiated pushes — see the roadmap note in the repository's `CLAUDE.md` and `docs/specs/dynamic-admin-mcp-primitives.md` for what's planned next.

## Settings

**Local development without auth**:

```python
UNFOLD_AGENTIC_LAYER_UNAUTHORIZED = True  # only honored when DEBUG = True
```

`/mcp/` requests without a token then act as the first active superuser (lowest pk); all permission filtering still runs against that real user. Ignored when `DEBUG = False`.

Configure the app with an `UNFOLD_AGENTIC_LAYER` dict in your project's settings — the same override-by-dict pattern Unfold itself uses for its own `UNFOLD` setting. Any key you omit falls back to its default. See `django_unfold_agentic_layer/conf.py` for the current list of settings; none are required for `/mcp/` to work.

```python
from datetime import timedelta

UNFOLD_AGENTIC_LAYER = {"SESSION_TTL": timedelta(hours=8)}  # MCP login lifetime, default 1 day
```

## Development

```bash
uv sync
cd packages/django-unfold-agentic-layer
uv run pytest
```

`django_test_app/` is a throwaway Django project (not a template for a real project) that the test suite boots to exercise this package end-to-end, including a real HTTP round-trip against `/mcp/` (see `tests/test_mcp_endpoint.py`).

See the [repository README](https://github.com/JargeZ/django-unfold-agentic-layer#readme) and `CLAUDE.md` for the broader architecture.
