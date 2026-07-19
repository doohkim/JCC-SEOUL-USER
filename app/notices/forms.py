"""공지사항 작성 폼."""

import nh3
from django import forms
from django.core.files.uploadedfile import UploadedFile
from tinymce.widgets import TinyMCE

from notices.models import Notice
from notices.services import compress_thumbnail
from users.models import Division

ALLOWED_BODY_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "span",
    "div",
    "ul",
    "ol",
    "li",
    "a",
    "img",
    "h1",
    "h2",
    "h3",
    "blockquote",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}
ALLOWED_BODY_ATTRS = {
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "title", "width", "height"},
    "*": {"style", "class"},
}


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = [
            "title",
            "body",
            "category",
            "thumbnail",
            "tags",
            "is_pinned",
            "scope",
            "division",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "maxlength": 200,
                    "autocomplete": "off",
                    "placeholder": "공지 제목을 입력하세요",
                }
            ),
            "body": TinyMCE(attrs={"id": "id_body"}),
            "category": forms.Select(),
            "thumbnail": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "tags": forms.TextInput(
                attrs={
                    "placeholder": "태그를 쉼표로 구분 (예: 수련회, 청년부)",
                    "autocomplete": "off",
                }
            ),
            "is_pinned": forms.CheckboxInput(),
            "scope": forms.RadioSelect(),
            "division": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["division"].required = False
        self.fields["category"].required = False
        self.fields["category"].queryset = Notice.active_categories()
        self.fields["category"].empty_label = "카테고리 선택"
        self.fields["division"].queryset = Division.objects.select_related(
            "region"
        ).order_by("region__sort_order", "sort_order", "name")
        self.fields["division"].empty_label = "지역·부서 선택"

    def clean_thumbnail(self):
        # 새로 업로드된 파일만 리사이즈/압축한다. (기존 파일 유지·삭제는 그대로)
        thumbnail = self.cleaned_data.get("thumbnail")
        if isinstance(thumbnail, UploadedFile):
            return compress_thumbnail(thumbnail)
        return thumbnail

    def clean_body(self):
        raw = self.cleaned_data.get("body") or ""
        return nh3.clean(
            raw,
            tags=ALLOWED_BODY_TAGS,
            attributes=ALLOWED_BODY_ATTRS,
            link_rel=None,
        )

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get("scope")
        division = cleaned.get("division")
        if scope == Notice.Scope.DIVISION and not division:
            self.add_error("division", "지역·부서를 선택하세요.")
        if scope == Notice.Scope.ALL:
            cleaned["division"] = None
        return cleaned
