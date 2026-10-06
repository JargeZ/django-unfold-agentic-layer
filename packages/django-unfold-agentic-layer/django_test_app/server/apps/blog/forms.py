from django import forms
from django.contrib.auth.models import User
from unfold.forms import ActionForm, BaseDialogForm

from .models import BlogPost


class BlogPostActionForm(ActionForm):
    """Django's changelist ``action_form`` with an extra field — shared by
    every bulk action of ``BlogPostAdmin``, read from ``request.POST``."""

    editor = forms.ModelChoiceField(queryset=User.objects.all(), required=False)


class DraftDialogForm(BaseDialogForm):
    title = forms.CharField(max_length=255)


class SetStatusDialogForm(BaseDialogForm):
    status = forms.ChoiceField(choices=BlogPost.Status.choices)


class AppendNoteDialogForm(BaseDialogForm):
    note = forms.CharField(help_text="Appended to the end of the post body.")
