"""조직 이동(같은 부서 팀 변경 / 부서 이전) 요청 시리얼라이저."""

from __future__ import annotations

from rest_framework import serializers

from registry.models import Member, MemberDivisionTeam
from registry.services.member_org import change_team_within_division, transfer_to_division
from users.models import Division, Team


class OrgChangeTeamSerializer(serializers.Serializer):
    """같은 부서 내 팀 변경."""

    member_id = serializers.IntegerField()
    division_id = serializers.IntegerField()
    new_team_id = serializers.IntegerField()
    membership_id = serializers.IntegerField(required=False, allow_null=True)
    make_primary = serializers.BooleanField(default=True)

    def validate(self, attrs):
        member = Member.objects.filter(pk=attrs["member_id"]).first()
        if not member:
            raise serializers.ValidationError({"member_id": "멤버가 없습니다."})
        division = Division.objects.filter(pk=attrs["division_id"]).first()
        if not division:
            raise serializers.ValidationError({"division_id": "부서가 없습니다."})
        team = Team.objects.filter(pk=attrs["new_team_id"]).select_related("division").first()
        if not team:
            raise serializers.ValidationError({"new_team_id": "팀이 없습니다."})
        if team.division_id != division.id:
            raise serializers.ValidationError(
                {"new_team_id": "팀이 해당 부서에 속하지 않습니다."}
            )
        membership = None
        mid = attrs.get("membership_id")
        if mid is not None:
            membership = MemberDivisionTeam.objects.filter(pk=mid, member=member).first()
            if not membership:
                raise serializers.ValidationError({"membership_id": "소속 행이 없습니다."})
        attrs["_member"] = member
        attrs["_division"] = division
        attrs["_team"] = team
        attrs["_membership"] = membership
        return attrs

    def save(self, **kwargs):
        d = self.validated_data
        return change_team_within_division(
            d["_member"],
            d["_division"],
            d["_team"],
            membership=d["_membership"],
            make_primary=d["make_primary"],
        )


class OrgTransferDivisionSerializer(serializers.Serializer):
    """부서 이전."""

    member_id = serializers.IntegerField()
    from_division_id = serializers.IntegerField(required=False, allow_null=True)
    to_division_id = serializers.IntegerField()
    team_id = serializers.IntegerField(required=False, allow_null=True)
    remove_from_source = serializers.BooleanField(default=True)
    make_primary = serializers.BooleanField(default=True)

    def validate(self, attrs):
        member = Member.objects.filter(pk=attrs["member_id"]).first()
        if not member:
            raise serializers.ValidationError({"member_id": "멤버가 없습니다."})
        to_div = Division.objects.filter(pk=attrs["to_division_id"]).first()
        if not to_div:
            raise serializers.ValidationError({"to_division_id": "목적 부서가 없습니다."})
        from_div = None
        fid = attrs.get("from_division_id")
        if fid is not None:
            from_div = Division.objects.filter(pk=fid).first()
            if not from_div:
                raise serializers.ValidationError({"from_division_id": "이전 부서가 없습니다."})
        team = None
        tid = attrs.get("team_id")
        if tid is not None:
            team = Team.objects.filter(pk=tid).select_related("division").first()
            if not team:
                raise serializers.ValidationError({"team_id": "팀이 없습니다."})
            if team.division_id != to_div.id:
                raise serializers.ValidationError(
                    {"team_id": "팀이 목적 부서에 속하지 않습니다."}
                )
        attrs["_member"] = member
        attrs["_from_division"] = from_div
        attrs["_to_division"] = to_div
        attrs["_team"] = team
        return attrs

    def save(self, **kwargs):
        d = self.validated_data
        return transfer_to_division(
            d["_member"],
            from_division=d["_from_division"],
            to_division=d["_to_division"],
            team=d["_team"],
            remove_from_source=d["remove_from_source"],
            make_primary=d["make_primary"],
        )
