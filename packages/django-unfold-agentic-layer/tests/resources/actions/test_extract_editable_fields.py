from django.contrib.admin import ModelAdmin
from django.http import HttpRequest
from django_unfold_agentic_layer.resources.actions.extract_editable_fields import (
    ExtractEditableFields,
)


def test_extract_editable_fields_for_create(
    blog_post_model_admin: ModelAdmin, admin_request: HttpRequest, snapshot
):
    infos = ExtractEditableFields().execute(blog_post_model_admin, admin_request, change=False)

    assert [info.model_dump() for info in infos] == snapshot


def test_extract_editable_fields_excludes_auto_now_add_field(
    blog_post_model_admin: ModelAdmin, admin_request: HttpRequest
):
    infos = ExtractEditableFields().execute(blog_post_model_admin, admin_request, change=False)

    assert "created_at" not in {info.name for info in infos}
