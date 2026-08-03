"""Shared pytest fixtures for django_unfold_agentic_layer tests.

As fixtures multiply, group them semantically (e.g. tests/fixtures/<topic>.py)
and re-export them here — see CLAUDE.md.
"""

import pytest
from django.contrib.auth.models import User


@pytest.fixture
def staff_user(db) -> User:
    return User.objects.create_superuser(username="staff", password="s3cret")  # noqa: S106


@pytest.fixture
def regular_user(db) -> User:
    return User.objects.create_user(username="regular", password="s3cret")  # noqa: S106
