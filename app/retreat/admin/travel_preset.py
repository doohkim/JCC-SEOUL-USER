from django import forms
from django.contrib import admin
from django.utils.html import format_html

from retreat.models import RetreatTravelPreset


@admin.register(RetreatTravelPreset)
class RetreatTravelPresetAdmin(admin.ModelAdmin):
    list_display = [
        "event",
        "direction",
        "label",
        "color_preview",
        "color",
        "code",
        "occurs_at",
        "sort_order",
        "is_active",
    ]
    list_editable = ["color"]
    list_display_links = ["event", "label"]
    list_filter = ["event", "direction", "is_active"]
    search_fields = ["label", "code", "event__name"]
    autocomplete_fields = ["event"]
    filter_horizontal = ["divisions"]
    ordering = ["event", "direction", "sort_order", "id"]
    fields = [
        "event",
        "direction",
        "code",
        "label",
        "color",
        "occurs_at",
        "divisions",
        "sort_order",
        "is_active",
    ]

    @admin.display(description="색상")
    def color_preview(self, obj):
        return format_html(
            '<span style="display:inline-block;width:1.1rem;height:1.1rem;'
            "border-radius:50%;background:{};border:1px solid #cbd5e1;"
            'vertical-align:middle"></span> <code>{}</code>',
            obj.color,
            obj.color,
        )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        if "code" in form.base_fields:
            form.base_fields["code"].help_text = (
                "예: advance, main, late, own_car, bus. "
                "코드에 own_car 또는 표시명에 '자차'가 있으면 "
                "달력에서 수동 입력(고정 시각 미적용)."
            )
        if "color" in form.base_fields:
            form.base_fields["color"].widget = forms.TextInput(
                attrs={
                    "class": "vTextField",
                    "placeholder": "#2563EB",
                    "style": "width:7rem",
                }
            )
            form.base_fields["color"].help_text = (
                "프리셋 태그에 사용할 #RRGGBB HEX 값을 직접 입력하세요."
            )
        if "occurs_at" in form.base_fields:
            form.base_fields["occurs_at"].required = False
            form.base_fields["occurs_at"].help_text = (
                "고정 웨이브 시각. 자차는 비워 두세요 — 조원이 달력으로 직접 선택합니다."
            )
        return form

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "color" and field is not None:
            field.widget = forms.TextInput(
                attrs={
                    "class": "vTextField",
                    "placeholder": "#2563EB",
                    "style": "width:7rem",
                    "maxlength": "7",
                }
            )
        return field
