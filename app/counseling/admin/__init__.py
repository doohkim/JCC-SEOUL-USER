from django.contrib import admin

from counseling.models import (
    PastorDayOverride,
    PastorScheduleSettings,
    CounselingRequest,
    CounselingSlot,
)


@admin.register(PastorScheduleSettings)
class PastorScheduleSettingsAdmin(admin.ModelAdmin):
    list_display = ("user_id", "default_start_hour", "default_end_hour", "slot_duration_minutes", "updated_at")
    raw_id_fields = ("user",)


@admin.register(PastorDayOverride)
class PastorDayOverrideAdmin(admin.ModelAdmin):
    list_display = ("pastor_id", "date", "is_closed", "updated_at")
    raw_id_fields = ("pastor",)


@admin.register(CounselingSlot)
class CounselingSlotAdmin(admin.ModelAdmin):
    list_display = ("pastor_id", "date", "start_time", "end_time", "state", "updated_at")
    list_filter = ("state", "date")
    raw_id_fields = ("pastor",)


@admin.register(CounselingRequest)
class CounselingRequestAdmin(admin.ModelAdmin):
    list_display = ("public_id", "applicant_id", "pastor_id", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("applicant", "pastor", "slot")
    readonly_fields = ("public_id", "created_at", "updated_at")
