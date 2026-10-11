"""Composite form fields (a ``MultiWidget`` that posts ``<name>_0``,
``<name>_1``: django-money's ``MoneyField``, Django's split datetime) take
one list item per part, through create, update and action dialog forms.
Like the admin itself, a date and time are read in the current time zone.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.utils.timezone import make_aware
from djmoney.money import Money
from server.apps.blog.models import UsagePackage

from tests.test_mcp_admin_tools import _call_tool, _rpc


@pytest.fixture
def usage_package(db):
    return UsagePackage.objects.create(
        name="Starter",
        price=Money("10.50", "USD"),
        starts_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
    )


@pytest.mark.django_db
def test_tool_schema_lists_composite_field_parts(client, bearer_login, staff_user):
    bearer_login(client, staff_user)

    tools = {t["name"]: t for t in _rpc(client, "tools/list")["tools"]}

    price = tools["create_blog_usagepackage"]["inputSchema"]["properties"]["price"]
    amount, currency = price["anyOf"][0]["prefixItems"]
    assert {"type": "number"} in amount["anyOf"]
    assert {"enum": ["EUR", "USD"], "type": "string"} in currency["anyOf"]


@pytest.mark.django_db
def test_create_and_update_composite_fields(client, bearer_login, staff_user):
    bearer_login(client, staff_user)

    created = _call_tool(
        client,
        "create_blog_usagepackage",
        {"name": "Pro", "price": [10.5, "EUR"], "starts_at": ["2026-02-01", "09:30"]},
    )
    assert created["success"] is True, created
    package = UsagePackage.objects.get(pk=created["pk"])
    assert package.price == Money("10.50", "EUR")
    assert package.starts_at == make_aware(datetime(2026, 2, 1, 9, 30))

    # Composite fields not provided keep their current values.
    renamed = _call_tool(client, "update_blog_usagepackage", {"pk": package.pk, "name": "Pro+"})
    assert renamed["success"] is True, renamed
    package.refresh_from_db()
    assert (package.name, package.price) == ("Pro+", Money("10.50", "EUR"))
    assert package.starts_at == make_aware(datetime(2026, 2, 1, 9, 30))

    repriced = _call_tool(
        client, "update_blog_usagepackage", {"pk": package.pk, "price": ["20", "USD"]}
    )
    assert repriced["success"] is True, repriced
    package.refresh_from_db()
    assert package.price == Money(Decimal("20"), "USD")


@pytest.mark.django_db
def test_update_user_keeps_its_split_datetime_fields(client, bearer_login, staff_user):
    # The User change form has last_login/date_joined as split datetimes.
    bearer_login(client, staff_user)

    result = _call_tool(client, "update_auth_user", {"pk": staff_user.pk, "first_name": "Ada"})

    assert result["success"] is True, result
    staff_user.refresh_from_db()
    assert staff_user.first_name == "Ada"


@pytest.mark.django_db
def test_action_dialog_form_takes_composite_field(client, bearer_login, staff_user, usage_package):
    bearer_login(client, staff_user)

    result = _call_tool(
        client,
        "run_blog_usagepackage_reschedule",
        {"pk": usage_package.pk, "starts_at": ["2026-03-01", "12:00"]},
    )

    assert result["success"] is True, result
    usage_package.refresh_from_db()
    assert usage_package.starts_at == make_aware(datetime(2026, 3, 1, 12, 0))


@pytest.mark.django_db
def test_detail_resource_reads_composite_fields(client, bearer_login, staff_user, usage_package):
    bearer_login(client, staff_user)

    result = _rpc(
        client, "resources/read", {"uri": f"dj-admin://blog/usagepackage/{usage_package.pk}/"}
    )

    data = json.loads(result["contents"][0]["text"])
    assert (data["price"], data["starts_at"]) == ("$10.50", "2026-01-01T10:00:00Z")
