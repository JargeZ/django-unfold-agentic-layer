<div align="center">

# 🔮 django-unfold-agentic-layer

**Turn your Django Unfold admin into an MCP server — AI agents get docs and your live admin, with your permissions**

[![PyPI](https://img.shields.io/pypi/v/django-unfold-agentic-layer?style=flat-square)](https://pypi.org/project/django-unfold-agentic-layer/)
[![Python](https://img.shields.io/pypi/pyversions/django-unfold-agentic-layer?style=flat-square)](https://pypi.org/project/django-unfold-agentic-layer/)
[![Last commit](https://img.shields.io/github/last-commit/JargeZ/django-unfold-agentic-layer?style=flat-square)](https://github.com/JargeZ/django-unfold-agentic-layer/commits/main)
[![Stars](https://img.shields.io/github/stars/JargeZ/django-unfold-agentic-layer?style=flat-square)](https://github.com/JargeZ/django-unfold-agentic-layer/stargazers)
[![Issues](https://img.shields.io/github/issues/JargeZ/django-unfold-agentic-layer?style=flat-square)](https://github.com/JargeZ/django-unfold-agentic-layer/issues)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](https://github.com/JargeZ/django-unfold-agentic-layer/pulls)
<br>
[![Django](https://img.shields.io/badge/Django-5.0+-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Unfold](https://img.shields.io/badge/Unfold-0.91+-6366f1?style=flat-square)](https://unfoldadmin.com)
[![MCP](https://img.shields.io/badge/MCP-Streamable_HTTP-4f46e5?style=flat-square)](https://modelcontextprotocol.io)
[![Claude Code](https://img.shields.io/badge/Claude_Code-ready-D97757?style=flat-square&logo=anthropic&logoColor=white)](https://code.claude.com)

**English** · [Русский](README.ru.md)

</div>

---

> [!WARNING]
> **The project is under active development.** APIs and behavior may change. Testing and feedback are very welcome — please [open an issue](https://github.com/JargeZ/django-unfold-agentic-layer/issues) if something breaks!

## ✨ What it is

A regular Django app. Add it to `INSTALLED_APPS`, include its `urls.py` — and your project serves an
MCP endpoint at `/mcp`. No separate process, works under both WSGI and ASGI.

- 📚 **Unfold docs for agents** — 25 tools with the official Django Unfold docs, so agents stop hallucinating settings and imports
- 🗂️ **Your admin, live** — every registered model as MCP resources (detail + list with your `list_filter`/search) and `create`/`update`/`delete` tools
- 🛡️ **Admin permissions apply** — an agent sees and does exactly what its user can do in the admin; validation goes through the model's admin form
- 🔐 **Standard MCP OAuth** — clients log in through your admin login + consent page, only active staff users

## 🚀 Installation

**Requirements:** Python 3.11+, Django 5.0+, `django-unfold` 0.91+.

**1. Install the package** from git:

```bash
# uv
uv add "django-unfold-agentic-layer @ git+https://github.com/JargeZ/django-unfold-agentic-layer.git#subdirectory=packages/django-unfold-agentic-layer"

# poetry
poetry add "git+https://github.com/JargeZ/django-unfold-agentic-layer.git#subdirectory=packages/django-unfold-agentic-layer"
```

Pin a branch, tag or commit with `.git@<ref>#subdirectory=…`.

**2. Add it to `settings.py`:**

```python
INSTALLED_APPS = [
    "unfold",  # before django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",  # required: /mcp authenticates staff users
    "django.contrib.contenttypes",
    "django.contrib.sessions",  # required: admin login in the OAuth flow
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_unfold_agentic_layer",  # exactly this string
    # your apps
]
```

`SessionMiddleware` and `AuthenticationMiddleware` must be in `MIDDLEWARE` (they are in any project with the admin).

**3. Include the URLs** in the project's root `urls.py`:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("django_unfold_agentic_layer.urls")),  # → /mcp, /mcp/o/…
]
```

> [!NOTE]
> Every route of the app lives under `mcp/`, so it won't collide with yours (e.g. django-oauth-toolkit at `/o/`).
> Need a prefix? `path("agent/", include(...))` gives `/agent/mcp`.

**4. Apply migrations** (OAuth clients and hashed tokens live in the app's own tables):

```bash
python manage.py migrate
```

## 🔌 Connecting clients

Clients log in on their own via standard MCP OAuth: the browser opens your admin login, then a consent page.

**Claude Code**

```bash
claude mcp add --transport http unfold https://your-project.example/mcp
# then in Claude Code: /mcp → unfold → Authenticate
```

**Cursor** — `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "unfold": { "url": "https://your-project.example/mcp" }
  }
}
```

**MCP Inspector** — for debugging:

```bash
npx @modelcontextprotocol/inspector
# Transport: Streamable HTTP, URL: http://localhost:8000/mcp
```

> [!TIP]
> Local development without OAuth — only honored when `DEBUG = True`:
>
> ```python
> UNFOLD_AGENTIC_LAYER_UNAUTHORIZED = True
> ```
>
> Requests without a token act as the first active superuser; permission filtering still applies.

> [!IMPORTANT]
> The issuer must be `https` (or `localhost`). Behind a proxy, set `SECURE_PROXY_SSL_HEADER` /
> `USE_X_FORWARDED_HOST` so Django builds correct absolute URLs.

## 🧰 What the agent gets

| Primitive | Example | What it does |
|---|---|---|
| 📚 Doc tools | `unfold_filters`, `unfold_search_docs` | Django Unfold docs, including all third-party integrations |
| 📄 Detail resource | `dj-admin://blog/blogpost/42/` | One object's fields as JSON + Markdown; FK/M2M as links |
| 📋 List resource | `dj-admin://blog/blogpost/{?params}` | Your `list_filter`/search params, `limit`/`offset`/`order_by` |
| ✏️ Tools | `create_blog_blogpost`, `update_blog_blogpost` | Through the admin form; errors come back per field |
| 🗑️ Tool | `delete_blog_blogpost` | Asks for confirmation before deleting |

Everything is filtered per request by `has_*_permission` — the agent never sees what its user can't do in the admin.

## 🔐 Access and sessions

- Only active **staff** users can log in; `is_active`/`is_staff` is re-checked on every request — un-staffing someone cuts off their tokens immediately.
- The Django session cookie does **not** authenticate `/mcp` — only the `Bearer` token does.
- A login lasts `SESSION_TTL` (default 1 day), no refresh tokens.
- Clients and tokens are visible in the admin — deleting one revokes it.

## ⚙️ Settings

All optional — an `UNFOLD_AGENTIC_LAYER` dict, the same override pattern as Unfold's `UNFOLD`:

```python
from datetime import timedelta

UNFOLD_AGENTIC_LAYER = {
    "SESSION_TTL": timedelta(hours=8),  # MCP login lifetime, default 1 day
    # CACHES alias that remembers answered confirmations of dangerous tools, so one
    # confirmation can't be replayed into many runs. Default "default" — with several
    # worker processes it must be a shared backend (Redis, DB, Memcached), not LocMem.
    "CONFIRMATION_CACHE": "default",
}
```

The full list is in [`conf.py`](packages/django-unfold-agentic-layer/src/django_unfold_agentic_layer/conf.py).

## 🗺️ Roadmap

- [ ] Admin actions (`@action`) as MCP tools
- [ ] Stateful mode / SSE for server-initiated notifications
- [ ] `allowed_hosts`/`allowed_origins` configuration via settings
- [ ] Custom field rendering

Details in [CLAUDE.md](CLAUDE.md) and [docs/specs](docs/specs/dynamic-admin-mcp-primitives.md).

## 🛠️ Development

The repo is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/); the package lives in `packages/django-unfold-agentic-layer/`.

```bash
uv sync
uvx pre-commit install   # secret scanning (gitleaks, trufflehog) + ruff on every commit
cd packages/django-unfold-agentic-layer
uv run pytest
```

The tests boot a throwaway Django project (`django_test_app/`) and drive real MCP requests through `/mcp`.
Architecture and conventions are in [CLAUDE.md](CLAUDE.md).

> [!TIP]
> **Developing with AI agents?** Give each agent its own isolated, disposable workspace — check out
> [**orca-recipes**](https://github.com/JargeZ/orca-recipes): per-workspace Docker environments for
> next-gen dev setups (Claude Code, Cursor, OpenCode). This repo ships one: `orca.yaml` + `dev.Dockerfile`.

## 🤝 Contributing

Issues and pull requests are welcome!

## 🙏 Credits

Inspired by [rissets/mcp-django-unfold](https://github.com/rissets/mcp-django-unfold) — the project that sparked the idea of building a full MCP compatibility layer for Django Unfold. The Unfold documentation skills are taken from that repository; everything else is a completely new implementation.

## 📄 License

[MIT](LICENSE)
