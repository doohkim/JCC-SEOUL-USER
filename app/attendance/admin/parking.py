from django.contrib import admin

from attendance.models import ParkingPermitApplication, ParkingPermitWindow
from users.admin.audit import AuditLoggingModelAdminMixin


@admin.register(ParkingPermitWindow)
class ParkingPermitWindowAdmin(AuditLoggingModelAdminMixin, admin.ModelAdmin):
    list_display = [
        "division",
        "weekday",
        "start_time",
        "end_time",
        "is_active",
    ]
    list_filter = ["division", "weekday", "is_active"]
    ordering = ["division", "weekday", "start_time"]
    autocomplete_fields = ["division"]


@admin.register(ParkingPermitApplication)
class ParkingPermitApplicationAdmin(AuditLoggingModelAdminMixin, admin.ModelAdmin):
    list_display = [
        "permit_date",
        "created_at",
        "user",
        "vehicle_number",
        "division",
        "team",
        "status",
    ]
    list_filter = ["permit_date", "status", "division", "team"]
    search_fields = ["user__username", "vehicle_number", "user__profile__display_name"]
    autocomplete_fields = ["user", "division", "team"]
