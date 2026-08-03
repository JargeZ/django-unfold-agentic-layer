"""Fixtures for the admin resource-generation module's tests.

blog_post_model_admin / blog_app_config expose the django_test_app's own
registered ModelAdmin and AppConfig — real admin metadata, not a fake stand-in.
"""

import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.admin import ModelAdmin
from server.apps.blog.apps import BlogConfig
from server.apps.blog.models import BlogPost


@pytest.fixture
def blog_post_model_admin() -> ModelAdmin:
    return admin.site._registry[BlogPost]


@pytest.fixture
def blog_app_config() -> BlogConfig:
    return apps.get_app_config("blog")
