"""Fixtures for the admin resource-generation module's tests.

blog_post_model_admin / blog_app_config expose the django_test_app's own
registered ModelAdmin and AppConfig — real admin metadata, not a fake stand-in.
"""

import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.auth.models import User
from django.http import HttpRequest, QueryDict
from server.apps.blog.apps import BlogConfig
from server.apps.blog.models import BlogPost


@pytest.fixture
def blog_post_model_admin() -> ModelAdmin:
    return admin.site._registry[BlogPost]


@pytest.fixture
def blog_app_config() -> BlogConfig:
    return apps.get_app_config("blog")


@pytest.fixture
def admin_request(staff_user: User) -> HttpRequest:
    """Minimal synthetic request a ``ChangeList`` needs: ``method``, ``user``,
    and a ``GET`` it can read query params from (see spec §6.1)."""
    request = HttpRequest()
    request.method = "GET"
    request.user = staff_user
    request.GET = QueryDict()
    return request


@pytest.fixture
def blog_posts_by_two_authors(staff_user: User, regular_user: User) -> list[BlogPost]:
    """Two distinct authors — which, incidentally, is also what gets the
    plain FK filter's ``RelatedFieldListFilter.has_output()`` to true: it
    lists choices from the *related* table's ``get_choices()`` (i.e. every
    ``User``, not just ones actually used by a ``BlogPost``), and is false
    whenever that table has fewer than 2 rows (see the docstring on
    ``ExtractListFilterFields`` — Django drops the filter from the
    changelist entirely below that bar, so a schema built against a near-empty
    test DB can be missing filters a real deployment would show)."""
    return [
        BlogPost.objects.create(title="First post", author=staff_user),
        BlogPost.objects.create(title="Second post", author=regular_user),
    ]
