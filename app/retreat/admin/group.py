from django.contrib import admin

from retreat.models import RetreatGroup, RetreatGroupMembership
from retreat.services.group_sync import delete_attendees_for_membership


class RetreatGroupMembershipInline(admin.TabularInline):
    model = RetreatGroupMembership
    extra = 0
    autocomplete_fields = ["user"]
    fields = ["user", "role"]


@admin.register(RetreatGroup)
class RetreatGroupAdmin(admin.ModelAdmin):
    list_display = ["event", "region", "division", "name", "order", "created_by"]
    list_filter = ["event", "region", "division"]
    list_editable = ["order"]
    ordering = ["event", "order", "id"]
    search_fields = ["name", "division__name", "region__name", "event__name"]
    autocomplete_fields = ["event", "region", "division"]
    readonly_fields = ["created_by", "created_at", "updated_at"]
    inlines = [RetreatGroupMembershipInline]

    def save_formset(self, request, form, formset, change):
        """인라인에서 운영진 행을 삭제하면 해당 조원 명단도 함께 제거."""
        if formset.model is RetreatGroupMembership:
            to_clean = [
                f.instance
                for f in formset.forms
                if getattr(f.instance, "pk", None) and f.cleaned_data.get("DELETE")
            ]
            super().save_formset(request, form, formset, change)
            for membership in to_clean:
                delete_attendees_for_membership(membership, changed_by=request.user)
        else:
            super().save_formset(request, form, formset, change)


@admin.register(RetreatGroupMembership)
class RetreatGroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["group", "user", "role"]
    list_filter = ["role", "group__event"]
    search_fields = ["user__username", "group__name"]
    autocomplete_fields = ["user", "group"]

    def delete_model(self, request, obj):
        """단건 삭제: 연결된 조원 명단 행도 함께 제거."""
        delete_attendees_for_membership(obj, changed_by=request.user)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """일괄 삭제: 각 운영진에 연결된 조원 명단 행도 함께 제거."""
        for obj in queryset:
            delete_attendees_for_membership(obj, changed_by=request.user)
        super().delete_queryset(request, queryset)
