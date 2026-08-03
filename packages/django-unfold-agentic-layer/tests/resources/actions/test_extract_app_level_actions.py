from django.contrib.admin import ModelAdmin
from django_unfold_agentic_layer.resources.actions.extract_app_level_actions import (
    ExtractAppLevelActions,
)


def test_extract_app_level_actions(blog_post_model_admin: ModelAdmin, snapshot):
    infos = ExtractAppLevelActions().execute(blog_post_model_admin)

    assert [info.model_dump() for info in infos] == snapshot
