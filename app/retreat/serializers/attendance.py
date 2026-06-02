from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatAttendance


class RetreatAttendanceSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    enrollment_id = serializers.IntegerField(source="enrollment.id", read_only=True)
    attendee_id = serializers.IntegerField(source="enrollment.source_attendee_id", read_only=True)
    session_id = serializers.IntegerField(source="enrollment.session_id", read_only=True)

    class Meta:
        model = RetreatAttendance
        fields = [
            "id",
            "enrollment",
            "enrollment_id",
            "attendee_id",
            "session_id",
            "status",
            "status_display",
            "note",
            "checked_at",
            "checked_by",
        ]
        read_only_fields = ["id", "status_display", "checked_at", "checked_by"]


class _BulkRowSerializer(serializers.Serializer):
    enrollment_id = serializers.IntegerField(required=False)
    attendee_id = serializers.IntegerField(required=False)
    status = serializers.ChoiceField(choices=RetreatAttendance.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate(self, attrs):
        if not attrs.get("enrollment_id") and not attrs.get("attendee_id"):
            raise serializers.ValidationError("enrollment_id 또는 attendee_id 가 필요합니다.")
        return attrs


class RetreatAttendanceBulkUpsertSerializer(serializers.Serializer):
    """세션 단위 일괄 출석 upsert 입력.

    예::

        {
          "session_id": 12,
          "rows": [
            {"attendee_id": 1, "status": "present"},
            {"attendee_id": 2, "status": "absent", "note": "감기"}
          ]
        }
    """

    session_id = serializers.IntegerField()
    rows = _BulkRowSerializer(many=True)

    def validate(self, attrs):
        rows = attrs.get("rows") or []
        seen = set()
        for r in rows:
            key = r.get("enrollment_id") or f"attendee:{r.get('attendee_id')}"
            if key in seen:
                raise serializers.ValidationError(
                    {"rows": f"{key} 가 중복 입력되었습니다."}
                )
            seen.add(key)
        return attrs
