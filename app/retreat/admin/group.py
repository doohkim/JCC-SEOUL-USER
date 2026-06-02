from django.contrib import admin

from retreat.models import RetreatGroup, RetreatGroupMembership


class RetreatGroupMembershipInline(admin.TabularInline):
    model = RetreatGroupMembership
    extra = 0
    autocomplete_fields = ["user"]
    fields = ["user", "role"]


@admin.register(RetreatGroup)
class RetreatGroupAdmin(admin.ModelAdmin):
    list_display = ["event", "region", "division", "name", "order"]
    list_filter = ["event", "region", "division"]
    list_editable = ["order"]
    ordering = ["event", "order", "id"]
    search_fields = ["name", "division__name", "region__name", "event__name"]
    autocomplete_fields = ["event", "region", "division"]
    inlines = [RetreatGroupMembershipInline]


@admin.register(RetreatGroupMembership)
class RetreatGroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["group", "user", "role"]
    list_filter = ["role", "group__event"]
    search_fields = ["user__username", "group__name"]
    autocomplete_fields = ["user", "group"]
