from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from retreat.models import RetreatCouncilMembership
from retreat.services.account_retired import ACCOUNT_RETIRED_DISPLAY, is_retired_user
from retreat.services.staff_application import primary_affiliation_for

User = get_user_model()


class RetreatCouncilMembershipSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_display_name = serializers.SerializerMethodField()
    user_real_name = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    user_region_id = serializers.SerializerMethodField()
    user_division_id = serializers.SerializerMethodField()
    user_account_retired = serializers.SerializerMethodField()
    user_account_retired_display = serializers.SerializerMethodField()
    user_is_pastoral = serializers.SerializerMethodField()
    user_affiliations = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    scope_label = serializers.CharField(read_only=True)
    region_name = serializers.CharField(
        source="region.name", read_only=True, default=""
    )
    division_name = serializers.CharField(
        source="division.name", read_only=True, default=""
    )

    class Meta:
        model = RetreatCouncilMembership
        fields = [
            "id",
            "user",
            "user_username",
            "user_display_name",
            "user_real_name",
            "user_phone",
            "user_region_id",
            "user_division_id",
            "user_account_retired",
            "user_account_retired_display",
            "user_is_pastoral",
            "user_affiliations",
            "role",
            "role_display",
            "region",
            "division",
            "region_name",
            "division_name",
            "scope_label",
            "note",
            "created_at",
        ]
        read_only_fields = ["scope_label", "region_name", "division_name"]

    def get_user_display_name(self, obj: RetreatCouncilMembership) -> str:
        profile = getattr(obj.user, "profile", None)
        if profile and getattr(profile, "real_name", ""):
            return profile.real_name
        return obj.user.username

    def get_user_real_name(self, obj: RetreatCouncilMembership) -> str:
        profile = getattr(obj.user, "profile", None)
        return (getattr(profile, "real_name", "") or "").strip()

    def get_user_phone(self, obj: RetreatCouncilMembership) -> str:
        profile = getattr(obj.user, "profile", None)
        return (getattr(profile, "phone", "") or "").strip()

    def get_user_region_id(self, obj: RetreatCouncilMembership) -> int | None:
        region, _division = primary_affiliation_for(obj.user)
        return region.id if region else None

    def get_user_division_id(self, obj: RetreatCouncilMembership) -> int | None:
        _region, division = primary_affiliation_for(obj.user)
        return division.id if division else None

    def get_user_account_retired(self, obj: RetreatCouncilMembership) -> bool:
        return is_retired_user(obj.user)

    def get_user_account_retired_display(self, obj: RetreatCouncilMembership) -> str:
        return ACCOUNT_RETIRED_DISPLAY if is_retired_user(obj.user) else ""

    def get_user_is_pastoral(self, obj: RetreatCouncilMembership) -> bool:
        role_code = getattr(getattr(obj.user, "role_level", None), "code", None)
        return role_code in {"pastor", "evangelist"}

    def get_user_affiliations(self, obj: RetreatCouncilMembership) -> list[dict]:
        user = obj.user
        rows = (
            user.division_teams.order_by(
                "-is_primary",
                "sort_order",
                "division__sort_order",
                "id",
            )
            .select_related("division", "division__region")
            .all()
        )
        values = [
            (
                row.division_id,
                row.division.region_id if row.division else None,
                row.division.name if row.division else "",
                (
                    row.division.region.name
                    if row.division and row.division.region_id
                    else ""
                ),
            )
            for row in rows
            if row.division_id
        ]
        seen = set()
        results = []
        for division_id, region_id, division_name, region_name in values:
            if division_id in seen:
                continue
            seen.add(division_id)
            results.append(
                {
                    "division_id": division_id,
                    "region_id": region_id,
                    "division_name": division_name or "",
                    "region_name": region_name or "",
                }
            )
        return results

    def validate(self, attrs):
        role = attrs.get("role") or getattr(self.instance, "role", None)
        region = attrs.get("region", getattr(self.instance, "region", None))
        division = attrs.get("division", getattr(self.instance, "division", None))
        if role in RetreatCouncilMembership.EVENT_WIDE_ROLES:
            if region or division:
                raise serializers.ValidationError(
                    "집회 전체·픽업 관찰 역할에는 담당 범위를 지정할 수 없습니다."
                )
        elif role in RetreatCouncilMembership.REGION_SCOPED_ROLES:
            if not region:
                raise serializers.ValidationError(
                    {"region": "지역 역할에는 담당 지역이 필요합니다."}
                )
            if division:
                raise serializers.ValidationError(
                    {"division": "지역 역할에는 부서를 지정할 수 없습니다."}
                )
        elif role in RetreatCouncilMembership.DIVISION_SCOPED_ROLES:
            if not division:
                raise serializers.ValidationError(
                    {"division": "부서 역할에는 담당 부서가 필요합니다."}
                )
        return attrs
