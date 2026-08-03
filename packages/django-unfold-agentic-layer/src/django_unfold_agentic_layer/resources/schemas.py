"""Pydantic schemas describing a Django admin app as an MCP-facing resource.

These are pure data — building them from a live ``admin.site`` registry is the
job of :mod:`django_unfold_agentic_layer.resources.actions`.
"""

from pydantic import BaseModel


class ActionInfo(BaseModel):
    """A single admin action, keyed by the name used to invoke it."""

    key: str
    title: str


class FilterFieldInfo(BaseModel):
    """A single field (or the search box) available for filtering a changelist."""

    key: str
    title: str
    format: str


class AdminModelResource(BaseModel):
    """One model registered in the admin, as exposed to an agent."""

    verbose_name: str
    verbose_name_plural: str
    each_model_actions: list[ActionInfo]
    app_level_actions: list[ActionInfo]
    filter_fields: list[FilterFieldInfo]


class AdminAppResource(BaseModel):
    """A Django app section of the admin, with all of its registered models."""

    title: str
    description: str | None
    models: list[AdminModelResource]
