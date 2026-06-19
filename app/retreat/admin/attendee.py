from django.contrib import admin

from retreat.models import RetreatAttendee


@admin.register(RetreatAttendee)
class RetreatAttendeeAdmin(admin.ModelAdmin):
    list_display = [
        "group",
        "name",
        "phone",
        "gender",
        "check_in_status",
        "participation_status",
        "checked_in_at",
        "checked_out_at",
        "sort_order",
        "created_by",
    ]
    list_filter = ["group__event", "group__region", "group__division", "gender"]
    search_fields = ["name", "phone", "group__name"]
    autocomplete_fields = ["group", "source_member"]
    readonly_fields = ["created_by", "created_at", "updated_at"]
