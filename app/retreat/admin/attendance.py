from django.contrib import admin

from retreat.models import RetreatAttendance, RetreatSessionAttendee


@admin.register(RetreatSessionAttendee)
class RetreatSessionAttendeeAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "name",
        "group_name",
        "region_name",
        "division_name",
        "check_in_status",
        "source_attendee",
    ]
    list_filter = [
        "session__event",
        "session",
        "check_in_status",
        "region_name",
        "division_name",
    ]
    search_fields = ["name", "phone", "group_name", "session__name"]
    autocomplete_fields = ["session", "source_attendee", "source_group"]
    readonly_fields = ["enrolled_at"]


@admin.register(RetreatAttendance)
class RetreatAttendanceAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "attendee_name",
        "group_name",
        "status",
        "checked_by",
        "checked_at",
    ]
    list_filter = ["enrollment__session__event", "enrollment__session", "status"]
    search_fields = [
        "enrollment__name",
        "enrollment__group_name",
        "enrollment__session__name",
    ]
    autocomplete_fields = ["enrollment", "checked_by"]
    readonly_fields = ["checked_at"]

    @admin.display(description="출석부")
    def session(self, obj):
        return obj.enrollment.session

    @admin.display(description="조원")
    def attendee_name(self, obj):
        return obj.enrollment.name

    @admin.display(description="조")
    def group_name(self, obj):
        return obj.enrollment.group_name
