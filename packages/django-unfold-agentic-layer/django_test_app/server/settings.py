"""Settings for the throwaway Django project used to exercise
django_unfold_agentic_layer against a real Unfold admin.

Modeled after django-modern-rest's `django_test_app` approach: a real,
end-to-end Django project (not an in-process settings stub) that pytest-django
boots for the test suite. Registers Unfold, the default User model, and a
BlogPost model so admin-facing behavior can be exercised for real. Not a
template for a real project's settings — see CLAUDE.md.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-unfold-agentic-layer-test-app"  # noqa: S105

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# pytest-django boots this settings module for the test suite, where an
# in-memory database (fast, isolated per process) is what's wanted. The
# Taskfile's `demo:*` tasks run manage.py directly against this same module
# for local migrate/runserver use, where a file-backed database is what's
# wanted instead, so they set DJANGO_TEST_APP_DB to a path relative to
# BASE_DIR (see Taskfile.yaml).
_test_app_db_name = os.environ.get("DJANGO_TEST_APP_DB")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / _test_app_db_name) if _test_app_db_name else ":memory:",
    }
}

INSTALLED_APPS = [
    # Unfold must precede django.contrib.admin so it can override admin templates.
    "unfold",
    "unfold.contrib.filters",  # AutocompleteSelectFilter, used by blog.BlogPostAdmin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "djangoql",  # DjangoQLSearchMixin on blog.BlogPostAdmin
    "django_unfold_agentic_layer",
    "server.apps.blog",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

ROOT_URLCONF = "server.urls"

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
