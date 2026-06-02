from django.contrib import admin

from retreat.models import RetreatEvent, RetreatSession


class RetreatSessionInline(admin.TabularInline):
    model = RetreatSession
    extra = 0
    fields = ["name", "sequence", "occurs_at", "location"]


@admin.register(RetreatEvent)
class RetreatEventAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    inlines = [RetreatSessionInline]


@admin.register(RetreatSession)
class RetreatSessionAdmin(admin.ModelAdmin):
    list_display = ["event", "name", "sequence", "occurs_at", "location"]
    list_filter = ["event"]
    search_fields = ["name", "event__name"]
    autocomplete_fields = ["event"]
