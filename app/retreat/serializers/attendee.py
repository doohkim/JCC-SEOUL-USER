from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatAttendee


class RetreatAttendeeSerializer(serializers.ModelSerializer):
    gender_display = serializers.CharField(source="get_gender_display", read_only=True)
    check_in_status_display = serializers.CharField(
        source="get_check_in_status_display", read_only=True
    )
    member_role_display = serializers.CharField(
        source="get_member_role_display", read_only=True
    )
    user_label = serializers.SerializerMethodField()
    lodging_room_label = serializers.SerializerMethodField()

    class Meta:
        model = RetreatAttendee
        fields = [
            "id",
            "group",
            "user",
            "user_label",
            "member_role",
            "member_role_display",
            "name",
            "phone",
            "gender",
            "gender_display",
            "memo",
            "check_in_status",
            "check_in_status_display",
            "expected_check_in_at",
            "expected_check_out_at",
            "checked_in_at",
            "checked_out_at",
            "source_member",
            "lodging_room",
            "lodging_room_label",
            "sort_order",
        ]
        read_only_fields = [
            "id",
            "gender_display",
            "check_in_status_display",
            "member_role_display",
            "user_label",
            "lodging_room_label",
        ]

    def get_user_label(self, attendee: RetreatAttendee) -> str:
        user = attendee.user
        if not user:
            return ""
        from users.services.user_display import user_display_name

        profile = getattr(user, "profile", None)
        real = (getattr(profile, "real_name", "") or "").strip()
        return real or user_display_name(user) or user.username

    def validate_name(self, value: str) -> str:
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("이름은 비워둘 수 없습니다.")
        return v

    def get_lodging_room_label(self, attendee: RetreatAttendee) -> str:
        room = attendee.lodging_room
        if not room:
            return ""
        lodging = getattr(room, "lodging", None)
        lname = getattr(lodging, "name", "") or ""
        return (f"{lname} {room.number}" if lname else room.number).strip()
