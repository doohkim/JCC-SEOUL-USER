from django.contrib import admin, messages

from retreat.models import RetreatAttendee
from retreat.services.group_sync import duplicate_event_attendees_for_user


@admin.register(RetreatAttendee)
class RetreatAttendeeAdmin(admin.ModelAdmin):
    list_display = [
        "group",
        "name",
        "phone",
        "gender",
        "effective_check_in_status",
        "participation_status",
        "checked_in_at",
        "checked_out_at",
        "sort_order",
        "created_by",
    ]
    list_filter = ["group__event", "group__region", "group__division", "gender"]
    search_fields = ["name", "phone", "group__name"]
    autocomplete_fields = ["group", "source_member"]
    readonly_fields = [
        "created_by",
        "created_at",
        "updated_at",
        "user_duplicate_warning",
    ]
    fields = [
        "group",
        "user",
        "name",
        "phone",
        "gender",
        "member_role",
        "check_in_status",
        "check_in_status_manually_set",
        "participation_status",
        "lodging_room",
        "lodging_stay_status",
        "checked_in_at",
        "checked_out_at",
        "expected_check_out_at",
        "sort_order",
        "source_member",
        "user_duplicate_warning",
        "created_by",
        "created_at",
        "updated_at",
    ]

    @admin.display(description="중복 조 경고")
    def user_duplicate_warning(self, obj: RetreatAttendee) -> str:
        if not obj.pk or not obj.user_id:
            return "—"
        others = duplicate_event_attendees_for_user(
            obj.user,
            event_id=obj.group.event_id,
            exclude_pk=obj.pk,
        )
        if not others:
            return "없음"
        parts = [f"{a.group.name} (조원 #{a.pk})" for a in others]
        return "⚠️ 같은 집회의 다른 조원 행: " + ", ".join(parts)

    @admin.display(description="입·퇴실 상태")
    def effective_check_in_status(self, obj: RetreatAttendee) -> str:
        from retreat.services.effective_check_in import effective_status_label

        return effective_status_label(obj)

    def save_model(self, request, obj, form, change):
        if "check_in_status" in form.changed_data:
            obj.check_in_status_manually_set = True
        super().save_model(request, obj, form, change)
        if not obj.user_id:
            return
        others = duplicate_event_attendees_for_user(
            obj.user,
            event_id=obj.group.event_id,
            exclude_pk=obj.pk,
        )
        if not others:
            return
        names = ", ".join(f"{a.group.name} (조원 #{a.pk})" for a in others)
        self.message_user(
            request,
            f"경고: 사용자 #{obj.user_id}이(가) 같은 집회에서 여러 조에 등록되어 있습니다: {names}",
            level=messages.WARNING,
        )
