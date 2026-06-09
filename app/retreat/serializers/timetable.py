from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatTimetableEntry


class RetreatTimetableEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = RetreatTimetableEntry
        fields = [
            "id",
            "day",
            "start_time",
            "end_time",
            "title",
            "location",
            "description",
            "sort_order",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_time": "종료 시각은 시작 시각보다 빠를 수 없습니다."}
            )
        return attrs
