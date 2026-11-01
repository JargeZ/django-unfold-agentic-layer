<div align="center">

### Your Django Unfold admin is already an MCP server

**Add one Django app — and AI agents can work with all your models, actions and permissions. Out of the box.**

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
> **Experiment. Do not use in production yet.** This project is an experiment with a large share of vibe ~~coding~~ engineering. APIs and behavior can change.
> But testing is very welcome — if something breaks, please [open an issue](https://github.com/JargeZ/django-unfold-agentic-layer/issues)!

## Live demo

Try it on a demo Unfold admin: <https://django-formula-admin-agentic.fly.dev/admin/> (login `demo` / `demo`).

```bash
claude mcp add --transport http unfold-mcp-demo "https://django-formula-admin-agentic.fly.dev/mcp/"
```

Then run `/mcp` in Claude Code, choose **Authenticate** and sign in with `demo` / `demo`. More about the demo: [JargeZ/formula](https://github.com/JargeZ/formula#readme).

## What it is

You already described your data in the admin: models, `list_filter`, search, forms, actions, permissions.
This app gives all of it to Claude, Cursor or any other MCP client. You do not write tools or a separate API.

Add it to `INSTALLED_APPS`, include its `urls.py` — and your project serves an MCP endpoint at `/mcp`.
No separate process, works under both WSGI and ASGI.

- **Your admin, live** — every registered model becomes MCP resources (detail + list with your `list_filter`/search) and `create`/`update`/`delete` tools
- **All your actions** — every admin and Unfold action becomes a tool, with its form as parameters
- **Your permissions** — an agent sees and does exactly what its user can do in the admin; validation goes through the model's admin form
- **Standard MCP OAuth** — clients log in through your admin login + consent page, only active staff users
- **Unfold docs for agents** — 25 tools with the official Django Unfold docs, so agents stop inventing settings and imports

## Installation

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
    path("", include("django_unfold_agentic_layer.urls")),  # → /mcp, /mcp/…
]
```

> [!NOTE]
> Every route of the app lives under `mcp/`, so it won't collide with yours (e.g. django-oauth-toolkit at `/o/`).
> Need a prefix? `path("agent/", include(...))` gives `/agent/mcp`.

**4. Apply migrations** (OAuth clients and hashed tokens live in the app's own tables):

```bash
python manage.py migrate
```

## Connecting clients

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
>
> Every such request logs a warning (`django_unfold_agentic_layer.mcp`), and a second one when it comes from a non-loopback address.
> The app also logs a warning once at startup (`django_unfold_agentic_layer.config`), because gunicorn and uvicorn do not run system checks.

### HTTPS and reverse proxies

MCP OAuth requires `https` (plain `http` works only on `localhost`/`127.0.0.1`). All OAuth URLs are
built from the incoming request with Django's standard `request.build_absolute_uri()`, so behind a
TLS-terminating proxy (nginx, Traefik, a PaaS load balancer) tell Django the original scheme — the
same setting the admin and CSRF already rely on:

```python
# settings.py — only if your proxy sets this header and strips it from client requests
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True  # only if the proxy rewrites Host
```

Without it, the OAuth endpoints answer `500` with `"error": "server_error"` and a description of
exactly this fix instead of advertising unusable `http://` URLs.

## What the agent gets

| Primitive | Example | What it does |
|---|---|---|
| Doc tools | `unfold_filters`, `unfold_search_docs` | Django Unfold docs, including all third-party integrations |
| Detail resource | `dj-admin://blog/blogpost/42/` | One object's fields as JSON + Markdown; FK/M2M as links (up to 100 per M2M field, with a note when there are more) |
| List resource | `dj-admin://blog/blogpost/{?params}` | Your `list_filter`/search params, `limit`/`offset`/`order_by` |
| Tools | `create_blog_blogpost`, `update_blog_blogpost` | Through the admin form; errors come back per field |
| Tool | `delete_blog_blogpost` | Asks for confirmation before deleting |
| Action tools | `run_blog_blogpost_publish_posts` | Every admin/Unfold action (bulk, list, row, detail) with its form; `DANGER` ones ask for confirmation |

By default users and groups are **not** exposed (`MODELS` setting) — opt them in deliberately.
Everything goes through the admin's own `has_*_permission` checks, re-run on every request — the agent never sees
or does what its user can't do in the admin right now; granting or revoking a permission applies to the very next call.
Writes run like the admin's own views: the same `save_model`/`save_related`/`delete_model` hooks in the same
transaction, the same history entries (an object's "History" shows what the agent changed, under its user), and a delete
is refused when it would cascade onto objects the user can't delete.

> [!IMPORTANT]
> The agent gets **exactly** the admin's permissions — including the admin's blind spots. Before you connect agents, check
> what a user can do in the browser: actions without `permissions=` run for view-only users; `UserAdmin` lets anyone with
> `change_user` set `is_superuser`; object permissions (e.g. django-guardian) apply only if your `get_queryset` and
> actions enforce them. Run `manage.py check --deploy` — it warns when confirmations are not shared between workers.

## Access and sessions

- On the consent page the user picks the login's **scopes**, on top of their own permissions: `mcp:read` (resources, always granted), `mcp:write` (create/update tools and actions) and `mcp:destructive` (delete tools and `DANGER` actions). Tools outside the scopes are not even listed, and every call re-checks its scope.
- Only active **staff** users holding the **`django_unfold_agentic_layer.use_mcp`** permission ("Can use the admin through MCP" — grant it per user or group; superusers always have it) can log in; `is_active`/`is_staff` and the permission are re-checked on every request — un-staffing someone or taking the permission away cuts off their tokens immediately. `REQUIRED_PERMISSION = False` lets every active staff user in.
- Changing a user's password revokes their MCP tokens, the same way Django logs out their browser sessions (the session auth hash; `SECRET_KEY_FALLBACKS` keeps them valid until the old key leaves it).
- The login (consent) page goes through `admin.site.admin_view`, so your admin site's own `has_permission` applies — a custom site's 2FA or IP rules guard the MCP login exactly like the admin.
- The consent page names where the code goes and warns about what it can't verify: a return address off your computer, an app's own scheme (`cursor://`), a self-declared client name — and suggests a separate, less privileged user to superusers.
- The Django session cookie does **not** authenticate `/mcp` — only the `Bearer` token does.
- A login lasts `SESSION_TTL` (default 1 day), no refresh tokens.
- An authorization code works once; presenting it again also revokes the token it was exchanged for (RFC 6749 §4.1.2).
- Clients and tokens are visible in the admin — deleting one revokes it. A deleted client gets a page asking the person to
  clear the saved authentication in their MCP client (Claude Code: `/mcp` → server → Clear authentication) and reconnect.

## Settings

All optional — an `UNFOLD_AGENTIC_LAYER` dict, the same override pattern as Unfold's `UNFOLD`:

```python
from datetime import timedelta

UNFOLD_AGENTIC_LAYER = {
    "SESSION_TTL": timedelta(hours=8),  # MCP login lifetime, default 1 day
    # CACHES alias that remembers answered confirmations of dangerous tools, so one
    # confirmation can't be replayed into many runs. Default "default" — with several
    # worker processes it must be a shared backend (Redis, DB, Memcached), not LocMem.
    "CONFIRMATION_CACHE": "default",
    # Only users with the use_mcp permission (superusers always) may use MCP. Default True.
    "REQUIRED_PERMISSION": True,
    # Which admin models MCP exposes: "app_label" or "app_label.model" entries.
    # INCLUDE None = all; EXCLUDE None = your user model and auth.group (so an agent can't
    # grant itself permissions); [] = exclude nothing.
    "MODELS": {"INCLUDE": None, "EXCLUDE": None},
    # True: create/update tools and every admin action ask the user to confirm first,
    # like delete tools and DANGER actions always do. Default False.
    "CONFIRM_WRITES": False,
}
```

The full list is in [`conf.py`](packages/django-unfold-agentic-layer/src/django_unfold_agentic_layer/conf.py).

### Logging

The library logs under `django_unfold_agentic_layer`, split by area. Configure them with Django's standard
[`LOGGING`](https://docs.djangoproject.com/en/stable/topics/logging/) setting — all at once by the parent name, or one area by its full name:

| Logger | What it reports |
|---|---|
| `django_unfold_agentic_layer.mcp` | Rejected `/mcp` calls (method + status at `WARNING`, response body at `DEBUG`), dev-mode warnings |
| `django_unfold_agentic_layer.oauth` | The OAuth flow: discovery, login, consent, tokens |
| `django_unfold_agentic_layer.tools` | Errors inside tool and resource handlers |
| `django_unfold_agentic_layer.builder` | Building the per-user server from the admin registry |
| `django_unfold_agentic_layer.config` | Unsafe settings, once at startup (the app's system-check warnings) |

```python
LOGGING = {
    "version": 1,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django_unfold_agentic_layer": {"handlers": ["console"], "level": "INFO"},
        # Response bodies can hold admin data: enable DEBUG only while debugging.
        "django_unfold_agentic_layer.mcp": {"level": "DEBUG"},
    },
}
```

## Production checklist

- Serve over **https** (behind a proxy: `SECURE_PROXY_SSL_HEADER`) and keep `ALLOWED_HOSTS` strict — OAuth URLs are built from the `Host` header.
- Grant `use_mcp` only to the people who should connect agents (`REQUIRED_PERMISSION`, on by default), ideally to dedicated users with just the permissions the agent needs — not superusers.
- Keep users and groups out of MCP (`MODELS`, the default) unless you mean it; narrow `MODELS["INCLUDE"]` to what agents need.
- Consider `CLOSED_CLIENT_REGISTRATION = True` and `CONFIRM_WRITES = True` for sensitive data.
- Point `CONFIRMATION_CACHE` at a cache all workers share and run `manage.py check --deploy`.
- Never set `UNFOLD_AGENTIC_LAYER_UNAUTHORIZED` outside local development.
- Rate-limit `/mcp/register` and `/mcp/token` at your proxy; collect `django_unfold_agentic_layer.*` logs.

## Roadmap

- [x] Admin actions (`@action`) as MCP tools
- [ ] Submit-line actions (`actions_submit_line`)
- [ ] Stateful mode / SSE for server-initiated notifications
- [ ] `allowed_hosts`/`allowed_origins` configuration via settings
- [ ] Custom field rendering

Details in [CLAUDE.md](CLAUDE.md) and [docs/specs](docs/specs/dynamic-admin-mcp-primitives.md).

## Development

The repo is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/); the package lives in `packages/django-unfold-agentic-layer/`.

```bash
uv sync
uv run pre-commit install   # secret scanning (gitleaks, trufflehog) + ruff, and a Conventional Commits check on messages
cd packages/django-unfold-agentic-layer
uv run pytest
```

The tests boot a throwaway Django project (`django_test_app/`) and drive real MCP requests through `/mcp`.
Architecture and conventions are in [CLAUDE.md](CLAUDE.md).

> [!TIP]
> **Developing with AI agents?** Give each agent its own isolated, disposable workspace — check out
> [**orca-recipes**](https://github.com/JargeZ/orca-recipes): per-workspace Docker environments for
> next-gen dev setups (Claude Code, Cursor, OpenCode). This repo ships one: `orca.yaml` + `dev.Dockerfile`.

## Contributing

Issues and pull requests are welcome!

## Credits

Inspired by [rissets/mcp-django-unfold](https://github.com/rissets/mcp-django-unfold) — the project that sparked the idea of building a full MCP compatibility layer for Django Unfold. The Unfold documentation skills are taken from that repository; everything else is a completely new implementation.

## License

[MIT](LICENSE)
