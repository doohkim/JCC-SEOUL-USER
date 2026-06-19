from __future__ import annotations

from datetime import datetime, timedelta

from rest_framework import serializers

from retreat.models import RetreatEvent, RetreatTimetableEntry


class RetreatTimetableEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = RetreatTimetableEntry
        fields = [
            "id",
            "day",
            "start_time",
            "end_day",
            "end_time",
            "title",
            "location",
            "description",
            "sort_order",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        day = attrs.get("day", getattr(self.instance, "day", None))
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        end_day = attrs.get("end_day", getattr(self.instance, "end_day", None))

        if "end_time" in attrs and attrs["end_time"] is None:
            attrs["end_day"] = None
            return attrs

        if end is None:
            if "end_day" in attrs:
                attrs["end_day"] = None
            return attrs

        if day is None or start is None:
            return attrs

        end_day_eff = end_day or day
        if end_day is None and end < start:
            end_day_eff = day + timedelta(days=1)
            attrs["end_day"] = end_day_eff
        elif end_day is None:
            attrs["end_day"] = None

        if end_day_eff < day:
            raise serializers.ValidationError(
                {"end_day": "종료 일자는 시작 일자보다 앞설 수 없습니다."}
            )

        start_dt = datetime.combine(day, start)
        end_dt = datetime.combine(end_day_eff, end)
        if end_dt <= start_dt:
            raise serializers.ValidationError(
                {"end_time": "종료 시각은 시작 시각보다 빠를 수 없습니다."}
            )

        event: RetreatEvent | None = self.context.get("event")
        if event is not None:
            if day < event.start_date or day > event.end_date:
                raise serializers.ValidationError(
                    {"day": "일자는 집회 기간 안에 있어야 합니다."}
                )
            max_end_day = event.end_date + timedelta(days=1)
            if end_day_eff < day or end_day_eff > max_end_day:
                raise serializers.ValidationError(
                    {"end_day": "종료 일자가 집회 기간을 벗어났습니다."}
                )

        if end_day_eff == day:
            attrs["end_day"] = None

        return attrs
