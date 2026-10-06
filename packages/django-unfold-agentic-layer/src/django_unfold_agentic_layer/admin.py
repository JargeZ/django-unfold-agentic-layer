"""Read-only admin over MCP OAuth state; deleting a row is how you revoke it.

Both admins are view + delete only: clients register themselves (RFC 7591)
and tokens come from the login flow, so there is nothing to add or edit by
hand. Deleting a client cascades to (revokes) all of its tokens.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from unfold.admin import ModelAdmin

from django_unfold_agentic_layer.models import OAuthClient, OAuthToken


class _ViewAndDeleteOnly:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OAuthClient)
class OAuthClientAdmin(_ViewAndDeleteOnly, ModelAdmin):
    list_display = ("client_name", "client_id", "active_tokens", "created_at")
    search_fields = ("client_id", "info__client_name")
    readonly_fields = ("client_id", "info", "created_at")
    ordering = ("-created_at",)

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
