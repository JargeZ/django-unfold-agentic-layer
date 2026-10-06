import copy
from typing import Any

from django.contrib.admin import ModelAdmin, helpers
from django.contrib.messages.storage.base import BaseStorage
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, QueryDict
from django.utils.datastructures import MultiValueDict
from django.utils.http import parse_header_parameters
from unfold.forms import BaseDialogForm

from django_unfold_agentic_layer.actions.base import BaseLogicAction
from django_unfold_agentic_layer.resources.actions.get_admin_model_instance import (
    GetAdminModelInstance,
)
from django_unfold_agentic_layer.resources.schemas import (
    ActionFile,
    ActionMessage,
    ActionResult,
    ActionToolInfo,
)

#: Larger files are reported by metadata only, so one export can't blow up
#: the agent's context.
MAX_INLINE_FILE_BYTES = 1024 * 1024

_TEXT_CONTENT_TYPES = {"application/json", "application/xml", "application/csv"}


class _CollectedMessages(BaseStorage):
    """In-memory ``django.contrib.messages`` storage: captures what the
    action reports, without persisting it into the MCP response's
    session/cookies the way the real storage backends would."""

    def _get(self, *args: Any, **kwargs: Any) -> tuple[list, bool]:
        return [], True

    def _store(self, messages: list, response: Any, *args: Any, **kwargs: Any) -> list:
        return []


class RunAdminAction(BaseLogicAction):
    """Runs one admin action (see ``ExtractActionTools``) the way the admin
    itself would, on a POST copy of ``request`` carrying the tool's
    arguments as form data:

    - ``bulk``: Django's own ``ModelAdmin.response_action()`` — it validates
      ``action_form``, re-checks the action against the user's permitted
      choices and selects the queryset from ``_selected_action`` pks;
    - ``model``/``instance``: the Unfold action method itself, whose
      decorator re-checks ``permissions`` (object-level for an instance) and
      binds the dialog form from ``request.POST``.

    Forms are validated here first as well, because on invalid input Django
    and Unfold only re-render HTML; doing it up front turns that into the
    same structured ``errors`` the create/update tools return. ``dry_run``
    stops right after that validation (``None`` if it passed), so a caller
    can reject bad input before asking the user to confirm.
    """

    def execute(
        self,
        model_admin: ModelAdmin,
        request: HttpRequest,
        action: ActionToolInfo,
        data: dict[str, Any],
        pk: str | None = None,
        pks: list[str] | None = None,
        dry_run: bool = False,
    ) -> ActionResult | None:
        if action.scope != "instance" and not model_admin.has_view_permission(request):
            raise PermissionDenied("You do not have permission to view this model.")
        post = self._form_data(data)
        action_request = copy.copy(request)
        action_request.method = "POST"
        action_request.POST = post
        action_request._files = MultiValueDict()  # FILES is a read-only property over this
        action_request._messages = messages = _CollectedMessages(action_request)

        if action.scope == "bulk":
            post.update({"action": action.name, "index": "0"})
            post.setlist(helpers.ACTION_CHECKBOX_NAME, pks or [])
            form = model_admin.action_form(post, auto_id=None)
            form.fields["action"].choices = model_admin.get_action_choices(request)
            if not pks:
                return ActionResult(
                    success=False,
                    errors={"pks": [{"message": "Select at least one item.", "code": "required"}]},
                )
            invalid_pks = [pk for pk in pks if not self._is_valid_pk(model_admin, pk)]
            if invalid_pks:
                return ActionResult(
                    success=False,
                    errors={
                        "pks": [
                            {
                                "message": f"Invalid primary key(s): {', '.join(invalid_pks)}.",
                                "code": "invalid",
                            }
                        ]
                    },
                )
            queryset = model_admin.get_queryset(action_request)
            # The admin silently skips pks it can't find; an agent should know.
            pk_field = model_admin.model._meta.pk
            found = set(queryset.filter(pk__in=pks).values_list("pk", flat=True))
            missing = [pk for pk in pks if pk_field.to_python(pk) not in found]
            if missing:
                return ActionResult(
                    success=False,
                    errors={
                        "pks": [
                            {
                                "message": f"No {model_admin.opts.verbose_name} found with "
                                f"pk(s): {', '.join(missing)}.",
                                "code": "not_found",
                            }
                        ]
                    },
                )
            if not form.is_valid():
                return ActionResult(
                    success=False, errors=form.errors.get_json_data(escape_html=True)
                )
            if dry_run:
                return None
            response = model_admin.response_action(action_request, queryset)
        else:
            if action.scope == "instance":
                GetAdminModelInstance().execute(model_admin, request, pk)
            unfold_action = model_admin.get_unfold_action(action.name)
            if unfold_action.dialog is not None:
                post["_form_submitted"] = "True"
                form_class = unfold_action.dialog.get("form_class") or BaseDialogForm
                form = form_class(data=post, request=action_request, object_id=pk)
                if not form.is_valid():
                    return ActionResult(
                        success=False, errors=form.errors.get_json_data(escape_html=True)
                    )
            if dry_run:
                return None
            kwargs = {"object_id": pk} if action.scope == "instance" else {}
            response = unfold_action.method(action_request, **kwargs)

        # A bulk action that returns nothing gets Django's redirect back to
        # the changelist — i.e. to this request's own path, meaningless here.
        if response is not None and response.get("Location") == action_request.get_full_path():
            response = None
        return self._result(response, messages)

    def _is_valid_pk(self, model_admin: ModelAdmin, pk: str) -> bool:
        # Without this a malformed pk reaches the ORM's pk__in lookup and
        # surfaces as a raw ValueError instead of a structured error.
        try:
            model_admin.model._meta.pk.to_python(pk)
        except ValidationError:
            return False
        return True

    def _form_data(self, data: dict[str, Any]) -> QueryDict:
        post = QueryDict(mutable=True)
        for key, value in data.items():
            if value is None or value is False:
                continue  # an unchecked checkbox simply isn't submitted
            if isinstance(value, list):
                post.setlist(key, [str(item) for item in value])
            else:
                post[key] = "on" if value is True else str(value)
        return post

    def _result(self, response: HttpResponse | None, messages: _CollectedMessages) -> ActionResult:
        collected = [ActionMessage(level=m.level_tag, message=str(m.message)) for m in messages]
        if response is None:
            return ActionResult(success=True, messages=collected)

        success = response.status_code < 400
        if 300 <= response.status_code < 400:
            return ActionResult(
                success=success, messages=collected, redirect_url=response.get("Location")
            )

        content_type = response.get("Content-Type", "")
        _disposition, disposition_params = parse_header_parameters(
            response.get("Content-Disposition", "")
        )
        mime_type = content_type.split(";")[0].strip()
        if not disposition_params.get("filename") and mime_type in ("", "text/html"):
            return ActionResult(success=success, messages=collected, returned_page=True)

        if hasattr(response, "render"):
            response.render()
        body = b"".join(response.streaming_content) if response.streaming else response.content
        file = ActionFile(
            filename=disposition_params.get("filename"), content_type=content_type, size=len(body)
        )
        if len(body) <= MAX_INLINE_FILE_BYTES:
            if (
                mime_type.startswith("text/")
                or mime_type in _TEXT_CONTENT_TYPES
                or mime_type.endswith("+json")
            ):
                file.text = body.decode(response.charset or "utf-8", errors="replace")
            else:
                file.content = body
        return ActionResult(success=success, messages=collected, file=file)
