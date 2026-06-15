from django.contrib import admin

from retreat.models import RetreatPickup, RetreatPickupLocation


@admin.register(RetreatPickup)
class RetreatPickupAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "direction",
        "number",
        "group",
        "name",
        "region",
        "division",
        "train_time",
        "boarding_place",
        "contact",
        "applicant_name",
    )
    list_filter = ("event", "direction", "group", "region", "division")
    search_fields = ("name", "contact", "boarding_place", "applicant_name")
    ordering = ("event", "direction", "number")


@admin.register(RetreatPickupLocation)
class RetreatPickupLocationAdmin(admin.ModelAdmin):
    list_display = ("event", "name", "sort_order", "created_by", "created_at")
    list_filter = ("event",)
    search_fields = ("name", "event__name")
    ordering = ("event", "sort_order", "name")
    readonly_fields = ("created_by", "created_at", "updated_at")
