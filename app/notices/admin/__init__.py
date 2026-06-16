from django.contrib import admin

from notices.models import Notice, NoticeCategory, TimetableEntry


@admin.register(NoticeCategory)
class NoticeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "color", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order", "name")


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "scope",
        "division",
        "is_pinned",
        "view_count",
        "created_by",
        "created_at",
    )
    list_filter = ("scope", "is_pinned", "category", "division__region", "created_at")
    search_fields = ("title", "body", "tags")
    readonly_fields = ("created_at", "updated_at", "view_count")
    raw_id_fields = ("created_by", "division")


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ("day", "start_time", "end_time", "title", "location", "sort_order")
    list_filter = ("day",)
    search_fields = ("title", "location", "description")
    ordering = ("day", "start_time", "sort_order")
