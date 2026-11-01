from django.conf import settings
from django.db import models


class OAuthClient(models.Model):
    """An MCP client registered through RFC 7591 dynamic client registration."""

    client_id = models.CharField(primary_key=True, max_length=255)
    #: ``mcp.shared.auth.OAuthClientInformationFull``, dumped as JSON.
    info = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "MCP client"

    def __str__(self) -> str:
        return self.info.get("client_name") or self.client_id


class OAuthToken(models.Model):
    """An authorization code, used-code marker or access token; only its
    sha256 is stored."""

    class Kind(models.TextChoices):
        CODE = "code"
        ACCESS = "access"
        #: An exchanged code, kept until its token expires so a replay can
        #: revoke that token (RFC 6749 §4.1.2); ``data`` names the token.
        USED_CODE = "used"

    token_hash = models.CharField(primary_key=True, max_length=64)
    kind = models.CharField(max_length=6, choices=Kind.choices)
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE)
    #: ``limit_choices_to``: who the consent page's autocomplete offers a
    #: superuser to issue a token for (see ``views/oauth.py``).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={"is_active": True, "is_staff": True},
    )
    #: The SDK's ``AuthorizationCode`` / ``AccessToken`` model, dumped as JSON.
    data = models.JSONField()
    #: An access token's ``user.get_session_auth_hash()`` at login: it covers
    #: the password, so a password change ends the login like it ends a session.
    session_auth_hash = models.CharField(max_length=128, blank=True, editable=False)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = "MCP access token"


class MCPAccess(models.Model):
    """No table: only carries the ``use_mcp`` permission, so it is granted
    like any other — per user or group, in the admin. See
    ``conf.Settings.REQUIRED_PERMISSION``."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [("use_mcp", "Can use the admin through MCP")]
