"""예배 출석 명단(구분·구성원)."""

from django.contrib import admin
from django.db.models import Count

from ..models import WorshipRosterEntry, WorshipRosterScope
from .audit import AuditLoggingModelAdminMixin


class JccModelAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}


class WorshipRosterEntryInline(admin.TabularInline):
    model = WorshipRosterEntry
    extra = 0
    autocomplete_fields = ["member", "team"]
    readonly_fields = ["first_imported_at", "last_imported_at"]
    fields = [
        "member",
        "team",
        "source_rel_path",
        "sheet_name",
        "first_imported_at",
        "last_imported_at",
    ]


@admin.register(WorshipRosterScope)
class WorshipRosterScopeAdmin(AuditLoggingModelAdminMixin, JccModelAdmin):
    list_display = [
        "division",
        "venue",
        "year",
        "session_part",
        "branch_label",
        "snapshot_label",
        "entry_count",
        "updated_at",
    ]
    list_filter = ["venue", "year", "division"]
    search_fields = ["branch_label", "division__name", "division__code"]
    autocomplete_fields = ["division"]
    inlines = [WorshipRosterEntryInline]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("division", "venue", "year")}),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": (
                    "session_part",
                    "branch_label",
                    "snapshot_label",
                    "sort_order",
                    "created_by",
                    "updated_by",
                ),
                "description": "온라인·지교회는 부=0. 인천 미구분 시 임포트에서 3부로 넣습니다.",
            },
        ),
    )
    readonly_fields = ["created_by", "updated_by"]

    @admin.display(description="인원")
    def entry_count(self, obj):
        return obj._entry_count

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_entry_count=Count("entries"))


@admin.register(WorshipRosterEntry)
class WorshipRosterEntryAdmin(AuditLoggingModelAdminMixin, JccModelAdmin):
    list_display = [
        "member",
        "scope",
        "team",
        "sheet_name",
        "last_imported_at",
    ]
    list_filter = ["scope__venue", "scope__year", "scope__division"]
    search_fields = ["member__name", "member__import_key", "source_rel_path"]
    autocomplete_fields = ["scope", "member", "team"]
    readonly_fields = [
        "first_imported_at",
        "last_imported_at",
        "created_by",
        "updated_by",
    ]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("scope", "member")}),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": (
                    "team",
                    "source_rel_path",
                    "sheet_name",
                    "first_imported_at",
                    "last_imported_at",
                    "created_by",
                    "updated_by",
                ),
            },
        ),
    )
