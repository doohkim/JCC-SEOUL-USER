"""공지사항 작성 폼."""

from django import forms

from notices.models import Notice


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ["title", "body", "is_pinned"]
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 200, "autocomplete": "off"}),
            "body": forms.Textarea(attrs={"rows": 12}),
            "is_pinned": forms.CheckboxInput(),
        }
