<div align="center">

# 🔮 django-unfold-agentic-layer

**Превращает вашу админку Django Unfold в MCP-сервер — AI-агенты получают документацию и живую админку с вашими правами**

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

[English](README.md) · **Русский**

</div>

---

> [!WARNING]
> **Проект в активной разработке.** API и поведение могут меняться. Тестирование и обратная связь очень приветствуются — если что-то сломалось, [заведите issue](https://github.com/JargeZ/django-unfold-agentic-layer/issues)!

## ✨ Что это

Обычное Django-приложение. Добавляете в `INSTALLED_APPS`, подключаете `urls.py` — и ваш проект отдаёт
MCP-эндпоинт `/mcp`. Без отдельного процесса, работает и под WSGI, и под ASGI.

- 📚 **Документация Unfold для агентов** — 25 инструментов с официальной документацией Django Unfold, агенты перестают выдумывать настройки и импорты
- 🗂️ **Ваша админка вживую** — каждая зарегистрированная модель как MCP-ресурсы (объект + список с вашими `list_filter`/поиском) и инструменты `create`/`update`/`delete`
- 🛡️ **Права из админки** — агент видит и делает ровно то, что может его пользователь в админке; валидация идёт через форму модели
- 🔐 **Стандартный MCP OAuth** — клиенты логинятся через ваш вход в админку + страницу подтверждения, только активные staff-пользователи

## 🚀 Установка

**Требования:** Python 3.11+, Django 5.0+, `django-unfold` 0.91+.

**1. Установите пакет** из git:

```bash
# uv
uv add "django-unfold-agentic-layer @ git+https://github.com/JargeZ/django-unfold-agentic-layer.git#subdirectory=packages/django-unfold-agentic-layer"

# poetry
poetry add "git+https://github.com/JargeZ/django-unfold-agentic-layer.git#subdirectory=packages/django-unfold-agentic-layer"
```

Зафиксировать ветку, тег или коммит: `.git@<ref>#subdirectory=…`.

**2. Добавьте в `settings.py`:**

```python
INSTALLED_APPS = [
    "unfold",  # до django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",  # обязательно: /mcp аутентифицирует staff-пользователей
    "django.contrib.contenttypes",
    "django.contrib.sessions",  # обязательно: вход в админку в OAuth-флоу
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_unfold_agentic_layer",  # именно эта строка
    # ваши приложения
]
```

В `MIDDLEWARE` должны быть `SessionMiddleware` и `AuthenticationMiddleware` (в любом проекте с админкой они уже есть).

**3. Подключите URL** в корневом `urls.py` проекта:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("django_unfold_agentic_layer.urls")),  # → /mcp, /mcp/o/…
]
```

> [!NOTE]
> Все маршруты приложения живут под `mcp/` и не пересекаются с вашими (например, django-oauth-toolkit на `/o/`).
> Нужен префикс? `path("agent/", include(...))` даст `/agent/mcp`.

**4. Примените миграции** (OAuth-клиенты и хэши токенов хранятся в собственных таблицах приложения):

```bash
python manage.py migrate
```

## 🔌 Подключение клиентов

Клиенты логинятся сами через стандартный MCP OAuth: в браузере открывается вход в вашу админку, затем страница подтверждения.

**Claude Code**

```bash
claude mcp add --transport http unfold https://your-project.example/mcp
# затем в Claude Code: /mcp → unfold → Authenticate
```

**Cursor** — `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "unfold": { "url": "https://your-project.example/mcp" }
  }
}
```

**MCP Inspector** — для отладки:

```bash
npx @modelcontextprotocol/inspector
# Transport: Streamable HTTP, URL: http://localhost:8000/mcp
```

> [!TIP]
> Локальная разработка без OAuth — работает только при `DEBUG = True`:
>
> ```python
> UNFOLD_AGENTIC_LAYER_UNAUTHORIZED = True
> ```
>
> Запросы без токена выполняются от первого активного суперпользователя; фильтрация по правам при этом сохраняется.

### 🌐 HTTPS и reverse proxy

MCP OAuth требует `https` (обычный `http` работает только на `localhost`/`127.0.0.1`). Все OAuth-URL
строятся из входящего запроса стандартным `request.build_absolute_uri()` Django, поэтому за
TLS-терминирующим прокси (nginx, Traefik, балансировщик PaaS) сообщите Django исходную схему — той же
настройкой, на которую уже опираются админка и CSRF:

```python
# settings.py — только если прокси выставляет этот заголовок и вырезает его из клиентских запросов
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True  # только если прокси переписывает Host
```

Без этого OAuth-эндпоинты отвечают `500` с `"error": "server_error"` и описанием именно этого
исправления, а не раздают нерабочие `http://` URL.

## 🧰 Что получает агент

| Примитив | Пример | Что делает |
|---|---|---|
| 📚 Инструменты документации | `unfold_filters`, `unfold_search_docs` | Документация Django Unfold, включая все сторонние интеграции |
| 📄 Ресурс объекта | `dj-admin://blog/blogpost/42/` | Поля объекта в JSON + Markdown; FK/M2M — ссылками |
| 📋 Ресурс списка | `dj-admin://blog/blogpost/{?params}` | Ваши параметры `list_filter`/поиска, `limit`/`offset`/`order_by` |
| ✏️ Инструменты | `create_blog_blogpost`, `update_blog_blogpost` | Через форму админки; ошибки возвращаются по полям |
| 🗑️ Инструмент | `delete_blog_blogpost` | Запрашивает подтверждение перед удалением |
| ⚡ Инструменты экшенов | `run_blog_blogpost_publish_posts` | Все экшены админки/Unfold (bulk, list, row, detail) с их формами; `DANGER` запрашивают подтверждение |

Всё проходит через собственные проверки админки `has_*_permission` на каждый запрос — агент не видит и не делает того,
чего его пользователь не может сделать в админке прямо сейчас; выдача или отзыв права применяются со следующего вызова.

## 🔐 Доступ и сессии

- Войти могут только активные **staff**-пользователи; `is_active`/`is_staff` перепроверяется на каждом запросе — снятие staff сразу отзывает токены.
- Сессионная cookie Django **не** аутентифицирует `/mcp` — только `Bearer`-токен.
- Логин живёт `SESSION_TTL` (по умолчанию 1 день), refresh-токенов нет.
- Клиенты и токены видны в админке — удаление = отзыв. Удалённый клиент увидит страницу с просьбой сбросить сохранённую
  авторизацию в MCP-клиенте (Claude Code: `/mcp` → сервер → Clear authentication) и подключиться заново.

## ⚙️ Настройки

Все необязательные — словарь `UNFOLD_AGENTIC_LAYER`, тот же паттерн переопределения, что у `UNFOLD` в самом Unfold:

```python
from datetime import timedelta

UNFOLD_AGENTIC_LAYER = {
    "SESSION_TTL": timedelta(hours=8),  # время жизни MCP-логина, по умолчанию 1 день
    # Алиас из CACHES, где хранятся уже принятые подтверждения опасных инструментов, —
    # чтобы одно подтверждение нельзя было переиграть в несколько запусков. По умолчанию
    # "default"; при нескольких воркерах нужен общий бэкенд (Redis, БД, Memcached), не LocMem.
    "CONFIRMATION_CACHE": "default",
}
```

Полный список — в [`conf.py`](packages/django-unfold-agentic-layer/src/django_unfold_agentic_layer/conf.py).

## 🗺️ Планы

- [x] Admin actions (`@action`) как MCP-инструменты
- [ ] Submit-line экшены (`actions_submit_line`)
- [ ] Stateful-режим / SSE для уведомлений от сервера
- [ ] Настройка `allowed_hosts`/`allowed_origins` через settings
- [ ] Кастомный рендеринг полей

Подробнее — в [CLAUDE.md](CLAUDE.md) и [docs/specs](docs/specs/dynamic-admin-mcp-primitives.md).

## 🛠️ Разработка

Репозиторий — [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/), пакет лежит в `packages/django-unfold-agentic-layer/`.

```bash
uv sync
uvx pre-commit install   # проверка секретов (gitleaks, trufflehog) + ruff на каждый коммит
cd packages/django-unfold-agentic-layer
uv run pytest
```

Тесты поднимают одноразовый Django-проект (`django_test_app/`) и гоняют реальные MCP-запросы через `/mcp`.
Архитектура и соглашения — в [CLAUDE.md](CLAUDE.md).

> [!TIP]
> **Ведёте разработку с агентами?** Дайте каждому агенту свою изолированную одноразовую среду —
> посмотрите [**orca-recipes**](https://github.com/JargeZ/orca-recipes): Docker-окружения на каждый
> workspace для next-gen сред разработки (Claude Code, Cursor, OpenCode). Здесь уже настроено: `orca.yaml` + `dev.Dockerfile`.

## 🤝 Участие

Issues и pull requests приветствуются!

## 🙏 Благодарности

Вдохновлено проектом [rissets/mcp-django-unfold](https://github.com/rissets/mcp-django-unfold) — именно он подал идею сделать полноценный слой совместимости MCP для Django Unfold. Скиллы по работе с Unfold взяты из оригинального репозитория, вся остальная реализация полностью новая.

## 📄 Лицензия

[MIT](LICENSE)
