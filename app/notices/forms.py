"""공지사항 작성 폼."""

from django import forms

from notices.models import Notice
from users.models import Division


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ["title", "body", "is_pinned", "scope", "division"]
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 200, "autocomplete": "off"}),
            "body": forms.Textarea(attrs={"rows": 12}),
            "is_pinned": forms.CheckboxInput(),
            "scope": forms.RadioSelect(),
            "division": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["division"].required = False
        self.fields["division"].queryset = Division.objects.select_related(
            "region"
        ).order_by("region__sort_order", "sort_order", "name")
        self.fields["division"].empty_label = "지역·부서 선택"

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get("scope")
        division = cleaned.get("division")
        if scope == Notice.Scope.DIVISION and not division:
            self.add_error("division", "지역·부서를 선택하세요.")
        if scope == Notice.Scope.ALL:
            cleaned["division"] = None
        return cleaned
