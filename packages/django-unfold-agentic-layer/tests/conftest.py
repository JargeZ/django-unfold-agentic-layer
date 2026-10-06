"""Shared pytest fixtures for django_unfold_agentic_layer tests.

As fixtures multiply, group them semantically (e.g. tests/fixtures/<topic>.py)
and re-export them here — see CLAUDE.md.
"""

import hashlib
import secrets
from datetime import timedelta

import pytest
from django.contrib.auth.models import Permission, User
from django.utils import timezone
from django_unfold_agentic_layer.models import OAuthClient, OAuthToken


@pytest.fixture(autouse=True)
def _clear_admin_mcp_instance_cache():
    """Busts BuildAdminMCPInstance's process-lifetime lru_cache between tests.

    Not pytest-antilru: that patches functools.lru_cache only for the
    duration of test *collection*, then restores it (see its
    pytest_collection hookwrapper). bridge.py — and therefore this cache — is
    only ever imported lazily, the first time a test actually calls
    client.post("/mcp/") (Django's URL conf resolves lazily), which happens
    during the *call* phase, well after antilru's patch window has already
    closed. The cache silently never gets registered for busting, and every
    test after the first ends up reusing whichever user/permission state was
    live when it was first built — a real, hard-to-notice cross-test leak
    (see build_admin_mcp_instance.py's own docstring). An explicit fixture
    doesn't depend on import timing at all.
    """
    yield
    from django_unfold_agentic_layer.mcp_server.builders.build_admin_mcp_instance import (
        _build_admin_mcp_instance,
    )

    _build_admin_mcp_instance.cache_clear()


@pytest.fixture
def staff_user(db) -> User:
    return User.objects.create_superuser(username="staff", password="s3cret")  # noqa: S106


@pytest.fixture
def regular_user(db) -> User:
    return User.objects.create_user(username="regular", password="s3cret")  # noqa: S106


@pytest.fixture
def staff_user_without_permissions(db) -> User:
    """Staff (can log into the admin at all), but zero model permissions —
    for asserting that permission-based filtering hides everything else."""
    return User.objects.create_user(
        username="staff-no-perms",
        password="s3cret",  # noqa: S106
        is_staff=True,
    )


@pytest.fixture
def blog_editor(db) -> User:
    """Staff with every ``blog`` model permission but not a superuser — sees
    all permission-gated admin actions except superuser-only ones."""
    user = User.objects.create_user(username="blog-editor", password="s3cret", is_staff=True)  # noqa: S106
    user.user_permissions.set(Permission.objects.filter(content_type__app_label="blog"))
    return user


@pytest.fixture
def blog_viewer(db) -> User:
    """Staff with only ``view_blogpost`` — sees the changelist but may not
    change posts through the regular change form."""
    user = User.objects.create_user(username="blog-viewer", password="s3cret", is_staff=True)  # noqa: S106
    user.user_permissions.set(Permission.objects.filter(codename="view_blogpost"))
    return user


@pytest.fixture
def bearer_login(db):
    """``bearer_login(client, user)`` — the MCP equivalent of ``client.force_login``:
    issues ``user`` a live OAuth access token (skipping the browser flow
    ``test_oauth.py`` covers) and sends it on every following request."""
    oauth_client, _ = OAuthClient.objects.get_or_create(
        client_id="test-client", defaults={"info": {}}
    )

    def login(client, user: User) -> None:
        token = secrets.token_urlsafe(32)
        OAuthToken.objects.create(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            kind=OAuthToken.Kind.ACCESS,
            client=oauth_client,
            user=user,
            data={"client_id": oauth_client.client_id, "scopes": []},
            expires_at=timezone.now() + timedelta(days=1),
        )
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    return login
