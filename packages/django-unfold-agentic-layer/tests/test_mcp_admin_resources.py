"""Real end-to-end checks that admin models surface as MCP resources through
the actual /mcp/ bridge — the dynamic counterpart to test_mcp_endpoint.py's
static-docs-tools checks.
"""

import json

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
def test_staff_user_without_permissions_sees_no_admin_resources(
    client, bearer_login, staff_user_without_permissions
):
    bearer_login(client, staff_user_without_permissions)

    result = _rpc(client, "resources/templates/list")

    assert result["resourceTemplates"] == []
