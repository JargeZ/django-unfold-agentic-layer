"""Real end-to-end checks that admin models surface as MCP resources through
the actual /mcp/ bridge — the dynamic counterpart to test_mcp_endpoint.py's
static-docs-tools checks.
"""

import json
from urllib.parse import quote

import pytest
from server.apps.blog.models import BlogPost

MCP_URL = "/mcp/"


def _rpc(client, method, params=None, request_id=1):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    response = client.post(
        MCP_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert "error" not in body, body
    return body["result"]


def _read_resource(client, uri):
    return _rpc(client, "resources/read", {"uri": uri})


@pytest.mark.django_db
def test_resource_templates_include_blog_post_detail_and_list(
    client, bearer_login, staff_user, regular_user
):
    # RelatedFieldListFilter.has_output() (Django's own filters.py) drops the
    # FK filter from the changelist entirely when the *related* table (User,
    # not BlogPost) has fewer than 2 rows — regular_user only exists here to
    # clear that bar so the filter shows up in the schema at all.
    bearer_login(client, staff_user)

    result = _rpc(client, "resources/templates/list")

    templates = {t["name"]: t["uriTemplate"] for t in result["resourceTemplates"]}
    assert templates["blog post"] == "dj-admin://blog/blogpost/{pk}/"

    list_template = templates["blog posts (list)"]
    assert list_template.startswith("dj-admin://blog/blogpost/{?")
    query_params = (
        list_template.removeprefix("dj-admin://blog/blogpost/{?").removesuffix("}").split(",")
    )
    assert set(query_params) == {
        "q",
        "djangoql",
        "author__id__exact",
        "author__isnull",
        "editor__id__exact",
        "editor__isnull",
        "has_editor",
        "status__exact",
        "status__isnull",
        "is_featured__exact",
        "is_featured__isnull",
        "created_at__gte",
        "created_at__lt",
        "limit",
        "offset",
        "order_by",
    }


@pytest.mark.django_db
def test_read_detail_resource_returns_json_and_markdown(client, bearer_login, staff_user):
    post = BlogPost.objects.create(title="Hello", body="World", author=staff_user)
    bearer_login(client, staff_user)

    result = _read_resource(client, f"dj-admin://blog/blogpost/{post.pk}/")

    contents_by_mime = {c["mimeType"]: c["text"] for c in result["contents"]}
    assert json.loads(contents_by_mime["application/json"]) == [
        {
            "pk": post.pk,
            "title": "Hello",
            "body": "World",
            "author": f"dj-admin://auth/user/{staff_user.pk}/",
            "editor": None,
            "status": "draft",
            "is_featured": False,
            "metadata": {},
        }
    ]
    assert result["_meta"] == {"total": 1, "count": 1}


@pytest.mark.django_db
def test_read_detail_resource_omits_fields_the_admin_hides(client, bearer_login, staff_user):
    # UserAdmin renders the password hash masked, so MCP must not leak it.
    bearer_login(client, staff_user)

    result = _read_resource(client, f"dj-admin://auth/user/{staff_user.pk}/")

    for content in result["contents"]:
        assert "password" not in content["text"]
        assert staff_user.password not in content["text"]


@pytest.mark.django_db
def test_read_detail_resource_for_missing_pk_is_an_mcp_error(client, bearer_login, staff_user):
    bearer_login(client, staff_user)

    response = client.post(
        MCP_URL,
        data=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/read",
                "params": {"uri": "dj-admin://blog/blogpost/999/"},
            }
        ),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200
    assert "error" in response.json()


@pytest.mark.django_db
def test_read_list_resource_applies_filter_order_and_limit(
    client, bearer_login, staff_user, regular_user
):
    BlogPost.objects.create(title="Alpha", author=staff_user)
    BlogPost.objects.create(title="Beta", author=regular_user)
    BlogPost.objects.create(title="Gamma", author=staff_user)
    bearer_login(client, staff_user)

    result = _read_resource(
        client,
        f"dj-admin://blog/blogpost/?author__id__exact={staff_user.pk}&order_by=-title&limit=1",
    )

    titles = [item["title"] for item in json.loads(result["contents"][0]["text"])]
    assert titles == ["Gamma"]
    # total reflects the filtered count (2 posts by staff_user), not the
    # limited page size (1) or the unfiltered table size (3).
    assert result["_meta"] == {"total": 2, "count": 1}


@pytest.mark.django_db
def test_read_list_resource_applies_custom_and_autocomplete_filters(
    client, bearer_login, staff_user, regular_user
):
    with_editor = BlogPost.objects.create(title="Edited", author=staff_user, editor=regular_user)
    BlogPost.objects.create(title="Unedited", author=staff_user)
    bearer_login(client, staff_user)

    # HasEditorFilter — a field-independent custom SimpleListFilter.
    result = _read_resource(client, "dj-admin://blog/blogpost/?has_editor=yes")
    titles = [item["title"] for item in json.loads(result["contents"][0]["text"])]
    assert titles == ["Edited"]

    # editor's AutocompleteSelectFilter — same query params as a plain FK
    # filter (unfold's own choices() shape is dropped, not surfaced as
    # FilterFieldInfo.choices, but the GET param itself still filters).
    result = _read_resource(
        client, f"dj-admin://blog/blogpost/?editor__id__exact={regular_user.pk}"
    )
    titles = [item["title"] for item in json.loads(result["contents"][0]["text"])]
    assert titles == ["Edited"]
    assert json.loads(result["contents"][0]["text"])[0]["pk"] == with_editor.pk


@pytest.mark.django_db
def test_read_list_resource_defaults_to_a_small_page_and_orders_by_pk(
    client, bearer_login, staff_user
):
    BlogPost.objects.bulk_create(BlogPost(title=str(i), author=staff_user) for i in range(25))
    bearer_login(client, staff_user)

    result = _read_resource(client, "dj-admin://blog/blogpost/")
    assert result["_meta"] == {"total": 25, "count": 20}

    result = _read_resource(client, "dj-admin://blog/blogpost/?order_by=-pk&limit=2")
    pks = [item["pk"] for item in json.loads(result["contents"][0]["text"])]
    assert pks == sorted(BlogPost.objects.values_list("pk", flat=True), reverse=True)[:2]


@pytest.mark.django_db
def test_read_list_resource_search_is_plain_by_default_and_djangoql_on_request(
    client, bearer_login, staff_user, regular_user
):
    BlogPost.objects.create(title="Django tips", author=staff_user)
    BlogPost.objects.create(title="Other", body="about django", author=regular_user)
    bearer_login(client, staff_user)

    def titles(query):
        result = _read_resource(client, f"dj-admin://blog/blogpost/?{query}&order_by=pk")
        return [item["title"] for item in json.loads(result["contents"][0]["text"])]

    # Like the admin with the DjangoQL toggle off: search_fields, icontains.
    assert titles("q=django") == ["Django tips", "Other"]
    query = quote(f'title ~ "django" and author.username = "{staff_user.username}"')
    assert titles(f"djangoql=on&q={query}") == ["Django tips"]


def _read_resource_error(client, uri):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": uri}}
    response = client.post(
        MCP_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )
    return response.json()["error"]["message"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "message"),
    [
        # Unfold's RelatedDropdownFilter declares __isnull but ignores it.
        ("editor__isnull=True", "Filter ignored editor__isnull='True'"),
        # A custom SimpleListFilter: only its declared lookups are valid.
        ("has_editor=maybe", "Filter ignored has_editor='maybe'"),
        ("order_by=nope", "Invalid order_by 'nope'. Allowed: pk, -pk, title, -title"),
        # DjangoQLSearchMixin reports a bad query as a message, not an error.
        ("djangoql=on&q=nope%20%3D%201", "Unknown field: nope"),
    ],
)
def test_read_list_resource_rejects_what_it_would_silently_ignore(
    client, bearer_login, staff_user, query, message
):
    bearer_login(client, staff_user)

    error = _read_resource_error(client, f"dj-admin://blog/blogpost/?{query}")

    assert message in error
    assert "<locals>" not in error


@pytest.mark.django_db
def test_staff_user_without_permissions_sees_no_admin_resources(
    client, bearer_login, staff_user_without_permissions
):
    bearer_login(client, staff_user_without_permissions)

    result = _rpc(client, "resources/templates/list")

    assert result["resourceTemplates"] == []
