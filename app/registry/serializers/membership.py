"""부서·팀 소속(MemberDivisionTeam) 조회용 시리얼라이저."""

from __future__ import annotations

from rest_framework import serializers

from registry.models import MemberDivisionTeam


class MemberDivisionTeamSerializer(serializers.ModelSerializer):
    division_name = serializers.CharField(source="division.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True, allow_null=True)

    class Meta:
        model = MemberDivisionTeam
        fields = [
            "id",
            "member",
            "division",
            "division_name",
            "team",
            "team_name",
            "is_primary",
            "sort_order",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "member",
            "division",
            "division_name",
            "team",
            "team_name",
            "is_primary",
            "sort_order",
            "created_at",
        ]
