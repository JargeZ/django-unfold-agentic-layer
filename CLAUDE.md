# CLAUDE.md

Guidance for working in this repository — a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) containing a single installable Django app that acts as an MCP server for the [Django Unfold](https://unfoldadmin.com) admin theme.

## What this repo is

`django-unfold-agentic-layer` is a normal Django app (`INSTALLED_APPS`) that *is* the MCP server — there is no separate process. A host project installs it as a pip dependency, adds it to `INSTALLED_APPS`, and includes its `urls.py`; that's what makes an MCP Streamable HTTP endpoint (`/mcp/`) available to AI clients, alongside whatever else the host project serves.

This replaces an earlier three-package design (a standalone stdio MCP server, a Django app speaking a hand-rolled pydantic RPC protocol, and a schemas package gluing the two together). That design existed to keep `uvx`-installable, Django-free MCP tooling separate from Django-installable app code. The new design collapses that split deliberately: MCP itself is the shared protocol now, so there's no more need for a custom envelope layer or a second distribution — see the "Roadmap note" below for what's still in progress.

| Concept | Value |
|---|---|
| PyPI / dist name | `django-unfold-agentic-layer` |
| Import name | `django_unfold_agentic_layer` |
| `INSTALLED_APPS` entry | `django_unfold_agentic_layer` (must equal `AppConfig.name` *and* `AppConfig.label` — see `apps.py`) |
| FastMCP server name (`FastMCP("...")`) | `django_unfold_agentic_layer` (`mcp_server/tools.py`) |

## Workspace mechanics

The root `pyproject.toml` is a *virtual* workspace root — no `[project]` table, just `[tool.uv.workspace]` and shared `[tool.ruff]` config. `packages/django-unfold-agentic-layer/` is currently the only workspace member, with its own `pyproject.toml`, `src/` layout, and `tests/`.

```bash
uv sync                                      # from repo root, syncs the workspace, one uv.lock
cd packages/django-unfold-agentic-layer && uv run pytest
```

## The MCP bridge (`mcp_server/`)

`src/django_unfold_agentic_layer/mcp_server/` holds the [`fastmcp`](https://gofastmcp.com)-based server:

- `tools.py` — the static `FastMCP` instance (`mcp`) holding the 25 documentation `@mcp.tool()`s.
- `docs.py` — pure data (`DOCS`, `ALL_SECTIONS`) backing the documentation tools.
- `builders/` — `BuildAdminMCPInstance` builds a **new**, per-`(user, admin_site)`, `lru_cache`-memoized `FastMCP` that mounts `tools.py`'s static server and adds dynamically-generated admin resources/tools (`Build*ResourceDefinition`/`Build*ToolDefinition`); see `docs/specs/dynamic-admin-mcp-primitives.md` for the design and `resources/actions/` for the Django-touching normalization/execution layer these builders consume.
- `bridge.py` — the Django-to-MCP delegation. Calls `BuildAdminMCPInstance` for the per-request server before entering async context (building it touches the ORM, and `_dispatch` runs inside an `async_to_sync`-created event loop where a direct ORM call would trip `SynchronousOnlyOperation`). **Does not use `FastMCP.http_app()`** — that assumes the parent ASGI app forwards its lifespan (`lifespan=mcp_app.lifespan`), which Django has no hook for. Instead, each request builds a fresh, stateless `StreamableHTTPSessionManager` and drives it with a synthetic ASGI scope reconstructed from ordinary `HttpRequest` attributes (method, headers, path, query string, etc. — not the live ASGI scope/receive channel), wrapped in `asgiref.sync.async_to_sync`. This is what makes `views/mcp.py` a plain synchronous Django view that works under **either WSGI or ASGI** deployment, with no new requirement on the host project's `asgi.py`/`wsgi.py`. Pattern adapted from [`gts360/django-mcp-server`](https://github.com/gts360/django-mcp-server).
- The session manager runs in **stateless, JSON-response mode**: no session persistence across requests (safe under multi-worker deployments), and POST responses are single-shot JSON rather than SSE streams. GET/DELETE are rejected — there's no session to listen on or tear down in stateless mode.
- A resource/tool handler that touches the ORM must move that work onto a thread-sensitive worker itself (`asgiref.sync.sync_to_async(fn, thread_sensitive=True)` from an `async def` handler) rather than trust fastmcp to offload it safely: fastmcp calls a resource template's function directly on the event-loop thread (no offload at all), and while it does offload a *sync* tool function, it uses a generic `anyio.to_thread` pool — a different, not-thread-consistent thread each call, which is liable to desync from Django's thread-local DB connection (surfaces as sqlite `"database is locked"` under a wrapping test transaction; a real backend may tolerate it, but the inconsistency is still there).

`views/mcp.py`'s `MCPView` gates `/mcp/` to active staff users holding an OAuth `Bearer` access token (401 + `WWW-Authenticate: Bearer resource_metadata=…` without one, 403 non-staff — JSON errors, not a login redirect, since MCP clients can't follow one). The Django session cookie deliberately does not authenticate `/mcp/`.

## OAuth (`oauth.py`, `views/oauth.py`, `models.py`)

Standard MCP authorization (OAuth 2.1, PKCE, RFC 7591 DCR) so clients (`claude mcp add` → Authenticate, Cursor, Inspector, …) log in on their own. The authorization server is the **MCP SDK's** (`mcp.server.auth.routes.create_auth_routes` — `/authorize`, `/token`, `/register`, `/revoke`), driven through `bridge.call_asgi` exactly like the MCP endpoint; it enforces PKCE, redirect_uri matching, code expiry and client auth. Keep our own security logic to storage + consent: `DjangoOAuthProvider` backs the SDK's `OAuthAuthorizationServerProvider` with `OAuthClient`/`OAuthToken` (sha256-hashed opaque tokens, Django async ORM), `authorize()` signs the request (`django.core.signing`) into a `staff_member_required` consent page, which issues the code. Consent is mandatory — registration is open, so it's the only thing stopping a drive-by flow against a logged-in staff user.

- **Every route stays under `mcp/`** (`mcp/o/…`) — never add anything at the host's root or at a bare `/o/` (host projects may run django-oauth-toolkit there). Discovery works without the root: PRM URL comes from the 401 header; the issuer (`<mcp>/o`) has a path, so clients' last fallback `<issuer>/.well-known/openid-configuration` lands on us (it carries dummy OIDC-required fields for the TS SDK's schema).
- No refresh tokens: `UNFOLD_AGENTIC_LAYER["SESSION_TTL"]` (default 1 day) is a hard cap on a login.
- `admin.py` lists clients and access tokens, view + delete only — deleting is revoking (a client's delete cascades to its tokens). `BuildAdminMCPInstance` skips this app's own models so an agent can never see or revoke MCP sessions through MCP.
- Not done: CIMD client IDs (spec 2025-11-25; `fastmcp.server.auth.cimd` has a fetcher), scopes.

## Testing conventions

Adapted from this account's global `test`/`test-fixtures` skills:

- Every module's tests live in its own `tests/`, with a `conftest.py` at that level. Once fixtures multiply, group them semantically (e.g. `tests/fixtures/<topic>.py`) and re-export with `from <pkg>.tests.fixtures import *` in `conftest.py` — do not do this prematurely while there's only a couple of fixtures.
- Each fixture should do exactly what its name says; build specific fixtures out of smaller reusable ones rather than one fixture with parameters for every case.
- Prefer a real, end-to-end check over an in-process approximation when the two would test meaningfully different things. `test_mcp_endpoint.py` drives real MCP JSON-RPC payloads through Django's actual request cycle (routing, auth, the view, the bridge, the session manager) via the Django test client — an in-process `mcp.list_tools()` call (`test_mcp_tools.py`) proves tool registration but not that the HTTP bridge itself works.
- Don't multiply near-duplicate tests for their own sake — it's fine to fold a few related assertions about one story into a single test.
- Once real API/business logic exists, prefer snapshot assertions (`syrupy`) over hand-written field-by-field assertions for response bodies, and use `pytest-recording`/VCR for tests that cross a real network boundary (mock at the integration's boundary, not throughout every caller).

## References — Django reusable-app & MCP packaging best practices

Consulted while designing this workspace:

- [Django docs: Advanced tutorial — how to write reusable apps](https://docs.djangoproject.com/en/5.2/intro/reusable-apps/) — canonical guidance on `AppConfig`, avoiding import-time side effects, and packaging for reuse.
- [`pydanny/cookiecutter-djangopackage`](https://github.com/pydanny/cookiecutter-djangopackage) — long-standing reference template for reusable Django app packages (tests dir, tox matrix, sane `setup.py`/PyPI metadata).
- [`wemake-services/django-modern-rest`](https://github.com/wemake-services/django-modern-rest) — modern (`uv`, `uv.lock`) Django library repo: installable package kept separate from a demo/test Django app used purely for integration testing, high test-coverage bar, `justfile` task runner. Its `dmr/settings.py` — a `Settings` `str` enum + `SettingsDict` `TypedDict` pair, kept in sync by module-level asserts — is the model for `django_unfold_agentic_layer/conf.py`'s typed settings keys.
- [`labd/django-healthchecks`](https://github.com/labd/django-healthchecks) (PyPI: `django-healthchecks`, import: `django_healthchecks`) — the model for `django_unfold_agentic_layer/urls.py`: a reusable app's `urls.py` exposes *only its own* views, never a bundled include of unrelated third-party apps like allauth. Not a dependency of this package.
- [Django Unfold](https://github.com/unfoldadmin/django-unfold) itself — `unfold.settings.get_config` is the model for `django_unfold_agentic_layer/conf.py`'s `UNFOLD_AGENTIC_LAYER` dict-override merge (deep-merges nested dicts rather than replacing them). `django-unfold` is a hard runtime dependency — the whole package targets Unfold specifically (e.g. `admin.py` uses `unfold.admin.ModelAdmin`).
- [`gts360/django-mcp-server`](https://github.com/gts360/django-mcp-server) — the reference implementation for `mcp_server/bridge.py`'s Django-request-to-`StreamableHTTPSessionManager` delegation pattern (manual ASGI scope reconstruction + `asgiref.sync.async_to_sync`, keeping the bridge WSGI/ASGI-agnostic).
- [`fastmcp`](https://github.com/PrefectHQ/fastmcp) / [FastMCP docs](https://gofastmcp.com) — the MCP server framework this package builds `mcp_server/tools.py` on; note the PyPI/import name is `fastmcp`, not the `mcp` SDK's own bundled `mcp.server.fastmcp.FastMCP`.
- [PyPA packaging guide: src layout](https://packaging.python.org/en/latest/tutorials/packaging-projects/) — why `src/<pkg>/` instead of a flat `<pkg>/` at repo root (prevents accidentally importing the uninstalled tree).
- [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) — the mechanism used to keep the workspace's lockfile and shared lint config in one place even with a single member today.

## Roadmap note

The `/mcp/` endpoint now dynamically exposes every admin-registered model the requesting user has permission on — detail/list resources, create/update tools, a confirm-before-delete tool, and a `run_*` tool per admin action (spec §14) — on top of the 25 static documentation tools, per `docs/specs/dynamic-admin-mcp-primitives.md`. `BuildAdminMCPInstance` (`mcp_server/builders/build_admin_mcp_instance.py`) is the entry point; `resources/actions/` holds the Django-touching normalization/execution layer per §0.1's builders-never-touch-Django invariant. Follow-ups, roughly in order:

- **Submit-line actions** — `actions_submit_line` run inside `save_model()` while saving a changeform, so they aren't exposed as `run_*` tools yet (every other action kind is). Two ways to add them are written up in `ExtractActionTools`'s docstring and spec §14.
- **Extensible field-type renderer registry** — `RenderModelInstanceMarkdown` ships one fixed, type-agnostic Markdown layout (spec §8.3 sketches a `conf.py`-driven per-field-type/widget registry); worth building once there's a second consumer that actually needs custom rendering.
- **Stateful mode / GET SSE support** — the bridge currently only supports stateless, single-shot POST calls. A stateful mode (session-pinned, with a real GET SSE listen stream for server-initiated pushes) is meaningful once tools need to stream or push notifications, but requires solving session affinity under multi-worker deployments first.
- **Production transport-security hardening** — `bridge.py` constructs its session manager with default (permissive) `TransportSecuritySettings`; a real deployment should be able to configure `allowed_hosts`/`allowed_origins` via `UNFOLD_AGENTIC_LAYER` settings (see `conf.py`).
