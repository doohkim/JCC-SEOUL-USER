from django.contrib import admin

from attendance.models import ParkingPermitApplication
from users.admin.audit import AuditLoggingModelAdminMixin


@admin.register(ParkingPermitApplication)
class ParkingPermitApplicationAdmin(AuditLoggingModelAdminMixin, admin.ModelAdmin):
    list_display = [
        "created_at",
        "user",
        "vehicle_number",
        "division",
        "team",
        "status",
    ]
    list_filter = ["status", "division", "team"]
    search_fields = ["user__username", "vehicle_number", "user__profile__display_name"]
    autocomplete_fields = ["user", "division", "team"]
