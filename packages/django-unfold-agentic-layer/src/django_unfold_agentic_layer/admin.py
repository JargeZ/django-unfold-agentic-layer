"""Admin over MCP OAuth state; deleting a row is how you revoke it.

Nothing is editable: clients register themselves (RFC 7591) and tokens come
from the login flow. Deleting a client cascades to (revokes) all of its
tokens. Clients can also be *added* by hand — the only way in once
``CLOSED_CLIENT_REGISTRATION`` is on.
"""

import time
import uuid

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import ValidationError
from unfold.admin import ModelAdmin

from django_unfold_agentic_layer.models import OAuthClient, OAuthToken


class _ViewAndDeleteOnly:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class OAuthClientAddForm(forms.ModelForm):
    """A public client (PKCE, no secret) — the same kind MCP clients
    register for themselves."""

    client_name = forms.CharField(max_length=255)
    redirect_uris = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=(
            "One per line, matched exactly, port included — e.g. "
            "http://localhost:33418/callback for "
            "`claude mcp add --client-id <id> --callback-port 33418 …`."
        ),
    )

    class Meta:
        model = OAuthClient
        fields = ()

    def clean(self):
        cleaned = super().clean()
        uris = [line.strip() for line in cleaned.get("redirect_uris", "").splitlines()]
        try:
            self.instance.info = OAuthClientInformationFull(
                client_id=str(uuid.uuid4()),
                client_id_issued_at=int(time.time()),
                client_name=cleaned.get("client_name"),
                redirect_uris=[uri for uri in uris if uri],
                token_endpoint_auth_method="none",  # noqa: S106 — public client, not a password
                grant_types=["authorization_code"],
                response_types=["code"],
            ).model_dump(mode="json")
        except ValidationError as error:
            raise forms.ValidationError(
                {"redirect_uris": f"Invalid redirect URI: {error.errors()[0]['msg']}."}
            ) from error
        self.instance.client_id = self.instance.info["client_id"]
        return cleaned


@admin.register(OAuthClient)
class OAuthClientAdmin(_ViewAndDeleteOnly, ModelAdmin):
    list_display = ("client_name", "client_id", "active_tokens", "created_at")
    search_fields = ("client_id", "info__client_name")
    readonly_fields = ("client_id", "info", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return ModelAdmin.has_add_permission(self, request)

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = OAuthClientAddForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        return ("client_name", "redirect_uris") if obj is None else self.readonly_fields

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else self.readonly_fields

    def get_queryset(self, request):
        live = Q(oauthtoken__kind=OAuthToken.Kind.ACCESS, oauthtoken__expires_at__gt=timezone.now())
        return (
            super().get_queryset(request).annotate(active_tokens=Count("oauthtoken", filter=live))
        )

    @admin.display(description="name", ordering="info__client_name")
    def client_name(self, obj: OAuthClient) -> str:
        return obj.info.get("client_name") or "—"

    @admin.display(description="active tokens", ordering="active_tokens")
    def active_tokens(self, obj: OAuthClient) -> int:
        return obj.active_tokens


@admin.register(OAuthToken)
class OAuthTokenAdmin(_ViewAndDeleteOnly, ModelAdmin):
    list_display = ("user", "client", "is_active", "expires_at")
    list_filter = ("client",)
    list_select_related = ("user", "client")
    search_fields = (f"user__{get_user_model().USERNAME_FIELD}", "client__info__client_name")
    fields = ("user", "client", "expires_at", "data")
    ordering = ("-expires_at",)

    def get_queryset(self, request):
        # Authorization codes live for minutes and aren't sessions; hide them.
        return super().get_queryset(request).filter(kind=OAuthToken.Kind.ACCESS)

    @admin.display(description="active", boolean=True)
    def is_active(self, obj: OAuthToken) -> bool:
        return obj.expires_at > timezone.now()
