from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatAttendee


class RetreatAttendeeSerializer(serializers.ModelSerializer):
    gender_display = serializers.CharField(source="get_gender_display", read_only=True)
    check_in_status_display = serializers.CharField(
        source="get_check_in_status_display", read_only=True
    )
    lodging_room_label = serializers.SerializerMethodField()

    class Meta:
        model = RetreatAttendee
        fields = [
            "id",
            "group",
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
            "lodging_room_label",
        ]

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
