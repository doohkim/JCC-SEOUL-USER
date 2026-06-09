from django.contrib import admin

from retreat.models import RetreatPickup


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
