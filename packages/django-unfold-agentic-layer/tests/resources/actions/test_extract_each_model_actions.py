from django.contrib.admin import ModelAdmin
from django.http import HttpRequest
from django_unfold_agentic_layer.resources.actions.extract_each_model_actions import (
    ExtractEachModelActions,
)


def test_extract_each_model_actions(
    blog_post_model_admin: ModelAdmin, admin_request: HttpRequest, snapshot
):
    infos = ExtractEachModelActions().execute(blog_post_model_admin, admin_request)

    assert [info.model_dump() for info in infos] == snapshot
