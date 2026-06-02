from django.contrib import admin

from retreat.models import RetreatCouncilMembership


@admin.register(RetreatCouncilMembership)
class RetreatCouncilMembershipAdmin(admin.ModelAdmin):
    list_display = ["event", "user", "role", "created_at"]
    list_filter = ["event", "role"]
    search_fields = ["user__username", "event__name"]
    autocomplete_fields = ["event", "user"]
