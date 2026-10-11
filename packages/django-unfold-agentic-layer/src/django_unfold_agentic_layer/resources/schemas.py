"""Pydantic schemas describing a Django admin app as an MCP-facing resource.

These are pure data — building them from a live ``admin.site`` registry is the
job of :mod:`django_unfold_agentic_layer.resources.actions`.
"""

import base64
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, WithJsonSchema


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
    python_type: Literal[
        "str", "int", "float", "bool", "choice", "related", "multi_related", "file"
    ]
    choices: list[tuple[str, str]] | None = None
    related_resource_uri: str | None = None


#: Strict base64: pydantic's own ``Base64Bytes`` silently drops non-alphabet
#: characters, so garbage would become an empty or corrupt file.
StrictBase64Bytes = Annotated[
    bytes,
    BeforeValidator(lambda value: base64.b64decode(value, validate=True)),
    WithJsonSchema({"type": "string", "format": "base64"}),
]


# Meant for small files: the whole content goes through the model's
# context, and Django's DATA_UPLOAD_MAX_MEMORY_SIZE limits the request body.
# (Comment, not docstring: pydantic sends the docstring to agents.)
#
# TODO: large files — fastmcp's ``FileUpload`` provider
# (https://gofastmcp.com/apps/providers/file-upload.md, fastmcp>=3.2, needs
# ``fastmcp[apps]``) lets the user drop files into an MCP Apps UI, so the
# content never goes through the model. To integrate it:
# - Subclass it and override ``_get_scope_key`` to return the OAuth token
#   subject: the default key is the MCP session ID, and our stateless bridge
#   gets a new one per request, so a file would not survive until the
#   create/update call.
# - Override ``on_store``/``on_list``/``on_read`` to keep files in Django's
#   ``default_storage`` (or the cache): the default in-memory store does not
#   work with multiple workers.
# - Let a file field also accept a reference to a stored upload (e.g.
#   ``{"upload": "<name>"}``), resolved to a ``File`` in ``split_uploads``.
# - Mount the provider in ``BuildAdminMCPInstance`` only for clients that
#   support MCP Apps; other clients do not show the UI.
class FileUploadInput(BaseModel):
    """A file to upload: its file name and its base64-encoded content."""

    name: str
    content: StrictBase64Bytes


class ActionToolInfo(BaseModel):
    """One admin action an agent can invoke as its own MCP tool.

    ``scope`` says what the action runs on, which decides the tool's
    leading parameter(s): ``bulk`` (Django's changelist ``actions``) takes
    ``pks``; ``instance`` (Unfold ``actions_row``/``actions_detail``) takes
    ``pk``; ``model`` (Unfold ``actions_list``) takes neither. ``fields`` are
    the action's form — an Unfold dialog's ``form_class``, or for bulk
    actions the ``ModelAdmin.action_form`` extras — as tool parameters.
    """

    tool_name: str
    #: Django's action key (bulk) or the ModelAdmin method name (Unfold).
    name: str
    title: str
    description: str
    scope: Literal["bulk", "model", "instance"]
    fields: list[EditableFieldInfo]
    #: ``variant=ActionVariant.DANGER`` — the tool asks for confirmation first.
    dangerous: bool


class ActionMessage(BaseModel):
    """A ``django.contrib.messages`` message the action added."""

    level: str
    message: str


class ActionFile(BaseModel):
    """A file the action responded with (e.g. an export). ``text`` is set for
    textual types, ``content`` for binary ones; both stay ``None`` when the
    file is over the inline size limit, leaving only its metadata."""

    filename: str | None
    content_type: str
    size: int
    text: str | None = None
    content: bytes | None = None


class ActionResult(BaseModel):
    """What running an admin action produced, normalized from the
    ``HttpResponse`` its handler returned (or ``None``)."""

    success: bool
    messages: list[ActionMessage] = []
    errors: dict | None = None
    redirect_url: str | None = None
    #: The handler returned an HTML page (an intermediate step meant for a browser).
    returned_page: bool = False
    file: ActionFile | None = None


class AdminModelResource(BaseModel):
    """One model registered in the admin, as exposed to an agent."""

    app_label: str
    model_name: str
    verbose_name: str
    verbose_name_plural: str
    description: str | None
    each_model_actions: list[ActionInfo]
    app_level_actions: list[ActionInfo]
    action_tools: list[ActionToolInfo]
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
