from django.contrib import admin

from retreat.models import RetreatTravelPreset


@admin.register(RetreatTravelPreset)
class RetreatTravelPresetAdmin(admin.ModelAdmin):
    list_display = [
        "event",
        "direction",
        "label",
        "code",
        "occurs_at",
        "sort_order",
        "is_active",
    ]
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
        "occurs_at",
        "divisions",
        "sort_order",
        "is_active",
    ]

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        if "code" in form.base_fields:
            form.base_fields["code"].help_text = (
                "예: advance, main, late, own_car, bus. "
                "코드에 own_car 또는 표시명에 '자차'가 있으면 "
                "달력에서 수동 입력(고정 시각 미적용)."
            )
        if "occurs_at" in form.base_fields:
            form.base_fields["occurs_at"].required = False
            form.base_fields["occurs_at"].help_text = (
                "고정 웨이브 시각. 자차는 비워 두세요 — 조원이 달력으로 직접 선택합니다."
            )
        return form
