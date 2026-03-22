"""주간 출석부 (주차 · 수·토 · 주일)."""

from django.contrib import admin
from django.db.models import Count

from attendance.models import AttendanceWeek, MidweekAttendanceRecord, SundayAttendanceLine
from users.admin.audit import AuditLoggingModelAdminMixin


class JccModelAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}


class MidweekAttendanceInline(admin.TabularInline):
    model = MidweekAttendanceRecord
    extra = 0
    autocomplete_fields = ["member"]
    fields = ["member", "service_type", "status"]


class SundayAttendanceInline(admin.TabularInline):
    model = SundayAttendanceLine
    extra = 0
    autocomplete_fields = ["member", "team"]
    fields = ["member", "venue", "session_part", "branch_label", "team"]


@admin.register(AttendanceWeek)
class AttendanceWeekAdmin(AuditLoggingModelAdminMixin, JccModelAdmin):
    list_display = [
        "division",
        "week_sunday",
        "auto_created",
        "midweek_count",
        "sunday_count",
        "updated_at",
    ]
    list_filter = ["division", "auto_created"]
    search_fields = ["division__name", "division__code", "note"]
    autocomplete_fields = ["division"]
    date_hierarchy = "week_sunday"
    inlines = [
        MidweekAttendanceInline,
        SundayAttendanceInline,
    ]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("division", "week_sunday")}),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": ("note", "auto_created", "created_by", "updated_by"),
            },
        ),
    )
    readonly_fields = ["created_by", "updated_by"]

    @admin.display(description="수·토 행")
    def midweek_count(self, obj):
        if hasattr(obj, "_midweek_count"):
            return obj._midweek_count
        return obj.midweek_records.count()

    @admin.display(description="주일 행")
    def sunday_count(self, obj):
        if hasattr(obj, "_sunday_count"):
            return obj._sunday_count
        return obj.sunday_lines.count()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _midweek_count=Count("midweek_records", distinct=True),
            _sunday_count=Count("sunday_lines", distinct=True),
        )


@admin.register(MidweekAttendanceRecord)
class MidweekAttendanceRecordAdmin(AuditLoggingModelAdminMixin, JccModelAdmin):
    list_display = ["week", "member", "service_type", "status", "updated_at"]
    list_filter = ["service_type", "status", "week__division"]
    search_fields = ["member__name", "member__import_key"]
    autocomplete_fields = ["week", "member"]
    readonly_fields = ["created_by", "updated_by"]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("week", "member", "service_type")}),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": ("status", "created_by", "updated_by"),
            },
        ),
    )


@admin.register(SundayAttendanceLine)
class SundayAttendanceLineAdmin(AuditLoggingModelAdminMixin, JccModelAdmin):
    list_display = [
        "week",
        "member",
        "venue",
        "session_part",
        "branch_label",
        "team",
        "updated_at",
    ]
    list_filter = ["venue", "week__division"]
    search_fields = ["member__name", "branch_label"]
    autocomplete_fields = ["week", "member", "team"]
    readonly_fields = ["created_by", "updated_by"]
    fieldsets = (
        (
            "필수",
            {"classes": ("jcc-required",), "fields": ("week", "member", "venue")},
        ),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": (
                    "session_part",
                    "branch_label",
                    "team",
                    "created_by",
                    "updated_by",
                ),
            },
        ),
    )
