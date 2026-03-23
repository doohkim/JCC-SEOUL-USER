"""수요·토요·주일 출석 — 예배일·부서 중심 (주차 테이블 없음)."""

import re

from django.contrib import admin

from attendance.models import MidweekAttendanceRecord, SundayAttendanceLine
from users.admin.audit import AuditLoggingModelAdminMixin

_WEEKDAY_KO = "월화수목금토일"


class JccModelAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}


@admin.register(MidweekAttendanceRecord)
class MidweekAttendanceRecordAdmin(AuditLoggingModelAdminMixin, JccModelAdmin):
    @staticmethod
    def _normalize_team_label(name: str) -> str:
        label = (name or "").strip()
        compact = re.sub(r"\s+", "", label)
        if compact in {"부서회장단", "팀회장단"}:
            return "회장단"
        return label

    list_display = [
        "division",
        "service_date",
        "weekday_ko",
        "service_type",
        "team_name_snapshot_display",
        "member",
        "status",
        "updated_at",
    ]
    list_filter = ["service_type", "status", "division"]
    search_fields = ["member__name", "member__import_key"]
    autocomplete_fields = ["division", "member"]
    readonly_fields = ["created_by", "updated_by"]
    date_hierarchy = "service_date"
    fieldsets = (
        (
            "필수",
            {
                "classes": ("jcc-required",),
                "fields": ("division", "service_date", "member", "service_type"),
            },
        ),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": (
                    "team",
                    "team_name_snapshot",
                    "status",
                    "created_by",
                    "updated_by",
                ),
            },
        ),
    )

    @admin.display(description="팀")
    def team_name_snapshot_display(self, obj: MidweekAttendanceRecord) -> str:
        return self._normalize_team_label(getattr(obj, "team_name_snapshot", "") or (obj.team.name if obj.team_id else ""))

    @admin.display(description="요일", ordering="service_date")
    def weekday_ko(self, obj):
        return _WEEKDAY_KO[obj.service_date.weekday()]


@admin.register(SundayAttendanceLine)
class SundayAttendanceLineAdmin(AuditLoggingModelAdminMixin, JccModelAdmin):
    @staticmethod
    def _normalize_team_label(name: str) -> str:
        label = (name or "").strip()
        compact = re.sub(r"\s+", "", label)
        if compact in {"부서회장단", "팀회장단"}:
            return "회장단"
        return label

    list_display = [
        "division",
        "service_date",
        "weekday_ko",
        "team_name_snapshot_display",
        "member",
        "venue",
        "session_part",
        "branch_label",
        "updated_at",
    ]
    list_filter = ["venue", "division"]
    search_fields = ["member__name", "branch_label"]
    autocomplete_fields = ["division", "member", "team"]
    readonly_fields = ["created_by", "updated_by"]
    date_hierarchy = "service_date"
    fieldsets = (
        (
            "필수",
            {
                "classes": ("jcc-required",),
                "fields": ("division", "service_date", "member", "venue"),
            },
        ),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": (
                    "session_part",
                    "branch_label",
                    "team",
                    "team_name_snapshot",
                    "created_by",
                    "updated_by",
                ),
            },
        ),
    )

    @admin.display(description="팀")
    def team_name_snapshot_display(self, obj: SundayAttendanceLine) -> str:
        return self._normalize_team_label(getattr(obj, "team_name_snapshot", "") or (obj.team.name if obj.team_id else ""))

    @admin.display(description="요일", ordering="service_date")
    def weekday_ko(self, obj):
        return _WEEKDAY_KO[obj.service_date.weekday()]
