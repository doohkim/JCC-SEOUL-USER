from django.contrib import admin

from notices.models import Notice, TimetableEntry


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "scope",
        "division",
        "is_pinned",
        "created_by",
        "created_at",
    )
    list_filter = ("scope", "is_pinned", "division__region", "created_at")
    search_fields = ("title", "body")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("created_by", "division")


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ("day", "start_time", "end_time", "title", "location", "sort_order")
    list_filter = ("day",)
    search_fields = ("title", "location", "description")
    ordering = ("day", "start_time", "sort_order")
