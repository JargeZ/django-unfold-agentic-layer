from django.urls import get_resolver, resolve, reverse
from django_unfold_agentic_layer import urls


def test_urlpatterns_defines_only_this_modules_own_routes():
    assert isinstance(urls.urlpatterns, list)
    assert len(urls.urlpatterns) == 1


def test_root_urlconf_resolves_without_import_errors():
    resolver = get_resolver()

    assert len(resolver.url_patterns) == 2


def test_mcp_route_resolves_through_the_real_root_urlconf():
    assert reverse("django_unfold_agentic_layer:mcp") == "/mcp/"
    assert resolve("/mcp/").url_name == "mcp"
