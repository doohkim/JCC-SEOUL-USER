"""출석 API 응답 시리얼라이저."""

from __future__ import annotations

import re

from rest_framework import serializers

from attendance.models import MidweekAttendanceRecord, SundayAttendanceLine
from users.models import Division, Team


class DivisionBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = ["id", "code", "name"]


class TeamBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "code", "name"]


class AttendanceWeekRollupSerializer(serializers.Serializer):
    week_sunday = serializers.CharField()
    division_code = serializers.CharField()
    division_name = serializers.CharField()
    sunday_line_count = serializers.IntegerField()
    midweek_record_count = serializers.IntegerField()
    wednesday_record_count = serializers.IntegerField()
    saturday_record_count = serializers.IntegerField()
    sunday_week_index_in_month = serializers.IntegerField()


class AttendanceWeekSummarySerializer(serializers.Serializer):
    week = serializers.DictField()
    worship_type = serializers.CharField()
    sunday = serializers.JSONField(allow_null=True)
    midweek = serializers.JSONField(allow_null=True)


class SundayAttendanceLineRowSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.name", read_only=True)
    venue_label = serializers.SerializerMethodField()
    team_name = serializers.SerializerMethodField()

    class Meta:
        model = SundayAttendanceLine
        fields = [
            "id",
            "service_date",
            "member_id",
            "member_name",
            "venue",
            "venue_label",
            "session_part",
            "branch_label",
            "team_id",
            "team_name",
        ]

    def get_venue_label(self, obj):
        return obj.get_venue_display()

    def get_team_name(self, obj):
        def normalize_team_label(name: str) -> str:
            label = (name or "").strip()
            compact = re.sub(r"\s+", "", label)
            if compact in {"부서회장단", "팀회장단"}:
                return "회장단"
            return label

        if getattr(obj, "team_name_snapshot", ""):
            return normalize_team_label(obj.team_name_snapshot)
        return normalize_team_label(obj.team.name) if obj.team_id else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if "service_date" in data and data["service_date"] is not None:
            data["service_date"] = instance.service_date.isoformat()
        return data


class MidweekRecordRowSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.name", read_only=True)
    team_name = serializers.SerializerMethodField()
    service_label = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = MidweekAttendanceRecord
        fields = [
            "id",
            "service_date",
            "member_id",
            "member_name",
            "team_name",
            "service_type",
            "service_label",
            "status",
            "status_label",
        ]

    def get_service_label(self, obj):
        return obj.get_service_type_display()

    def get_status_label(self, obj):
        return obj.get_status_display() if obj.status else None

    def get_team_name(self, obj):
        def normalize_team_label(name: str) -> str:
            label = (name or "").strip()
            compact = re.sub(r"\s+", "", label)
            if compact in {"부서회장단", "팀회장단"}:
                return "회장단"
            return label

        if getattr(obj, "team_name_snapshot", ""):
            return normalize_team_label(obj.team_name_snapshot)
        if getattr(obj, "team_id", None):
            return normalize_team_label(obj.team.name)
        return normalize_team_label(getattr(obj, "member_team_label", None))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if "service_date" in data and data["service_date"] is not None:
            data["service_date"] = instance.service_date.isoformat()
        return data


class AttendanceMetaSerializer(serializers.Serializer):
    worship_types = serializers.ListField(child=serializers.DictField())
    venues = serializers.ListField(child=serializers.DictField())
    midweek_service_types = serializers.ListField(child=serializers.DictField())
    midweek_statuses = serializers.ListField(child=serializers.DictField())
