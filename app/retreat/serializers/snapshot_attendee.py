"""마감 출석부 전용 스냅샷 조원 시리얼라이저."""

from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatAttendee, RetreatSessionAttendee


class RetreatSessionAttendeeAdminSerializer(serializers.ModelSerializer):
    """출석부에만 존재하는 조원 스냅샷 (source_attendee 없음)."""

    is_snapshot_only = serializers.BooleanField(read_only=True, default=True)
    session_id = serializers.IntegerField(source="session.id", read_only=True)
    check_in_status_display = serializers.CharField(
        source="get_check_in_status_display", read_only=True
    )

    class Meta:
        model = RetreatSessionAttendee
        fields = [
            "id",
            "session_id",
            "name",
            "phone",
            "gender",
            "memo",
            "check_in_status",
            "check_in_status_display",
            "sort_order",
            "is_snapshot_only",
        ]
        read_only_fields = [
            "id",
            "session_id",
            "is_snapshot_only",
            "check_in_status_display",
        ]

    def validate_name(self, value: str) -> str:
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("이름은 비워둘 수 없습니다.")
        return v

    def validate_check_in_status(self, value: str) -> str:
        if value not in dict(RetreatAttendee.CheckInStatus.choices):
            raise serializers.ValidationError("올바르지 않은 입·퇴실 상태입니다.")
        return value
