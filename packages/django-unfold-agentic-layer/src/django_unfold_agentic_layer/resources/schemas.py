"""Pydantic schemas describing a Django admin app as an MCP-facing resource.

These are pure data — building them from a live ``admin.site`` registry is the
job of :mod:`django_unfold_agentic_layer.resources.actions`.
"""

from typing import Literal

from pydantic import BaseModel


class ActionInfo(BaseModel):
    """A single admin action, keyed by the name used to invoke it."""

    key: str
    title: str


class FilterChoiceInfo(BaseModel):
    """One value an agent could plug into a filter's GET parameter.

    Mirrors Django's own ``ListFilter.choices()`` output (``display`` +
    ``query_string``) verbatim rather than inventing a new shape for it.
    """

    display: str
    query_string: str


class FilterFieldInfo(BaseModel):
    """A single, real GET parameter accepted by a changelist filter or the
    search box — one entry per element of the filter's ``expected_parameters()``
    (a single ``list_filter`` entry can expect more than one, e.g. a FK's
    companion ``__isnull`` parameter, or a split date/time range's four).
    """

    key: str
    title: str
    format: str
    choices: list[FilterChoiceInfo] | None = None
    related_resource_uri: str | None = None


class EditableFieldInfo(BaseModel):
    """A single field an agent can set when creating/updating an instance —
    sourced from ``ModelAdmin.get_form()`` (spec §7.1), so exclusions
    (``auto_now(_add)``, readonly fields, admin-level ``fields``/``exclude``)
    are already applied; nothing here is guessed from raw model attributes.

    ``python_type`` intentionally stays coarse (``str`` covers most fields,
    Django's own ``form.is_valid()`` does the real parsing/validation) —
    see the Field/Annotated appendix's "keep the mapping shallow" note.
    """

    name: str
    title: str
    required: bool
    help_text: str
    python_type: Literal["str", "int", "float", "bool", "choice", "related", "multi_related"]
    choices: list[tuple[str, str]] | None = None
    related_resource_uri: str | None = None


class AdminModelResource(BaseModel):
    """One model registered in the admin, as exposed to an agent."""

    app_label: str
    model_name: str
    verbose_name: str
    verbose_name_plural: str
    description: str | None
    each_model_actions: list[ActionInfo]
    app_level_actions: list[ActionInfo]
    filter_fields: list[FilterFieldInfo]
    sortable_fields: list[str]
    list_per_page: int
    create_fields: list[EditableFieldInfo]
    update_fields: list[EditableFieldInfo]
    can_add: bool
    can_change: bool
    can_delete: bool


class AdminAppResource(BaseModel):
    """A Django app section of the admin, with all of its registered models."""

    title: str
    description: str | None
    models: list[AdminModelResource]
