from django.contrib import admin

from counseling.models import (
    CounselorDayOverride,
    CounselorScheduleSettings,
    CounselingRequest,
    CounselingSlot,
)


@admin.register(CounselorScheduleSettings)
class CounselorScheduleSettingsAdmin(admin.ModelAdmin):
    list_display = ("user_id", "default_start_hour", "default_end_hour", "slot_duration_minutes", "updated_at")
    raw_id_fields = ("user",)


@admin.register(CounselorDayOverride)
class CounselorDayOverrideAdmin(admin.ModelAdmin):
    list_display = ("counselor_id", "date", "is_closed", "updated_at")
    raw_id_fields = ("counselor",)


@admin.register(CounselingSlot)
class CounselingSlotAdmin(admin.ModelAdmin):
    list_display = ("counselor_id", "date", "start_time", "end_time", "state", "updated_at")
    list_filter = ("state", "date")
    raw_id_fields = ("counselor",)


@admin.register(CounselingRequest)
class CounselingRequestAdmin(admin.ModelAdmin):
    list_display = ("public_id", "applicant_id", "counselor_id", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("applicant", "counselor", "slot")
    readonly_fields = ("public_id", "created_at", "updated_at")
