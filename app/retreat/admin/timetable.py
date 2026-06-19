from django.contrib import admin

from retreat.models import RetreatTimetableEntry


@admin.register(RetreatTimetableEntry)
class RetreatTimetableEntryAdmin(admin.ModelAdmin):
    list_display = [
        "event",
        "day",
        "start_time",
        "end_day",
        "end_time",
        "title",
        "location",
    ]
    list_filter = ["event", "day"]
    search_fields = ["title", "location", "event__name"]
    autocomplete_fields = ["event"]
    ordering = ["event", "day", "start_time", "sort_order"]
