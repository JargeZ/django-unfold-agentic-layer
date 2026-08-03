from django.urls import path

from django_unfold_agentic_layer.views.mcp import MCPView

app_name = "django_unfold_agentic_layer"

urlpatterns = [
    path("mcp/", MCPView.as_view(), name="mcp"),
]
