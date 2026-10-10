from django.contrib.admin import ModelAdmin
from django.http import HttpRequest

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.schemas import FilterFieldInfo

#: Our name for djangoql's ``q-l`` GET param: a hyphen is not valid in a
#: URI template variable or a Python parameter. ApplyMCPFiltersToRequest
#: renames it back.
DJANGOQL_PARAM = "djangoql"

_DJANGOQL_SYNTAX = (
    'DjangoQL query, e.g. title ~ "django" and author.username = "admin"; '
    "operators = != ~ !~ > >= < <= in, not in, and, or, parentheses; "
    "None, True, False; related fields with a dot"
)


class ExtractSearchFilterField(BaseLogicAction):
    """The search box, if ``ModelAdmin.get_search_fields()`` is non-empty.

    With djangoql's ``DjangoQLSearchMixin`` (detected by duck typing, so
    djangoql stays optional): stub ``search_fields`` only means ``q`` is
    always DjangoQL; own ``search_fields`` mean the admin's plain/DjangoQL
    toggle, exposed as the extra ``djangoql`` param (plain search by default).
    """

    def execute(self, model_admin: ModelAdmin, request: HttpRequest) -> list[FilterFieldInfo]:
        search_fields = model_admin.get_search_fields(request)
        if not search_fields:
            return []

        if not hasattr(model_admin, "djangoql_search_enabled"):
            return [self._plain(search_fields)]
        if not model_admin.search_mode_toggle_enabled():
            return [FilterFieldInfo(key="q", title="Search", format=_DJANGOQL_SYNTAX)]
        return [
            self._plain(search_fields, f". Set {DJANGOQL_PARAM}=on to send a DjangoQL query"),
            FilterFieldInfo(
                key=DJANGOQL_PARAM,
                title="DjangoQL search",
                format=f"optional; on = read q as a {_DJANGOQL_SYNTAX}",
            ),
        ]

    def _plain(self, search_fields: list[str], suffix: str = "") -> FilterFieldInfo:
        fields = ", ".join(search_fields)
        return FilterFieldInfo(
            key="q", title="Search", format=f"free-text search across: {fields}{suffix}"
        )
