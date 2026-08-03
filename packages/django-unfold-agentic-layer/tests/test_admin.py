import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from server.apps.blog.models import BlogPost
from unfold.admin import ModelAdmin


def test_user_is_registered_with_unfold_admin():
    assert isinstance(admin.site._registry[User], ModelAdmin)


def test_blog_post_is_registered_with_unfold_admin():
    assert isinstance(admin.site._registry[BlogPost], ModelAdmin)


@pytest.mark.django_db
def test_blog_post_round_trips_through_the_database():
    author = User.objects.create_user(username="agent", password="s3cret")  # noqa: S106
    post = BlogPost.objects.create(title="Hello, Unfold", author=author)

    assert BlogPost.objects.get(pk=post.pk).author == author
