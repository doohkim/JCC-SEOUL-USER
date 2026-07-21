from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from retreat.models import RetreatCouncilMembership
from retreat.services.account_retired import ACCOUNT_RETIRED_DISPLAY, is_retired_user

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
    user_role_level = serializers.SerializerMethodField()
    user_role_level_name = serializers.SerializerMethodField()
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
            "user_role_level",
            "user_role_level_name",
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

    @staticmethod
    def _division_team_rows_for(user):
        prefetched = getattr(user, "prefetched_division_teams", None)
        if prefetched is not None:
            return prefetched
        return list(
            user.division_teams.order_by(
                "-is_primary",
                "sort_order",
                "division__sort_order",
                "id",
            )
            .select_related("division", "division__region")
            .all()
        )

    def _affiliation_bundle_for(self, user) -> dict:
        cache = getattr(self, "_user_affiliation_cache", None)
        if cache is None:
            cache = {}
            self._user_affiliation_cache = cache
        key = user.id
        if key in cache:
            return cache[key]

        rows = self._division_team_rows_for(user)
        seen = set()
        affiliations = []
        primary_region_id = None
        primary_division_id = None
        for row in rows:
            division = getattr(row, "division", None)
            division_id = row.division_id
            if not division_id or not division:
                continue
            if primary_division_id is None:
                primary_division_id = division_id
                primary_region_id = division.region_id
            if division_id in seen:
                continue
            seen.add(division_id)
            affiliations.append(
                {
                    "division_id": division_id,
                    "region_id": division.region_id,
                    "division_name": division.name or "",
                    "region_name": (
                        division.region.name
                        if division.region_id and getattr(division, "region", None)
                        else ""
                    ),
                }
            )

        bundle = {
            "region_id": primary_region_id,
            "division_id": primary_division_id,
            "affiliations": affiliations,
        }
        cache[key] = bundle
        return bundle

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
        return self._affiliation_bundle_for(obj.user)["region_id"]

    def get_user_division_id(self, obj: RetreatCouncilMembership) -> int | None:
        return self._affiliation_bundle_for(obj.user)["division_id"]

    def get_user_account_retired(self, obj: RetreatCouncilMembership) -> bool:
        return is_retired_user(obj.user)

    def get_user_account_retired_display(self, obj: RetreatCouncilMembership) -> str:
        return ACCOUNT_RETIRED_DISPLAY if is_retired_user(obj.user) else ""

    def get_user_is_pastoral(self, obj: RetreatCouncilMembership) -> bool:
        role_code = getattr(getattr(obj.user, "role_level", None), "code", None)
        return role_code in {"pastor", "evangelist"}

    def get_user_role_level(self, obj: RetreatCouncilMembership) -> int | None:
        level = getattr(getattr(obj.user, "role_level", None), "level", None)
        return int(level) if level is not None else None

    def get_user_role_level_name(self, obj: RetreatCouncilMembership) -> str:
        return (
            getattr(getattr(obj.user, "role_level", None), "name", "") or ""
        ).strip()

    def get_user_affiliations(self, obj: RetreatCouncilMembership) -> list[dict]:
        return self._affiliation_bundle_for(obj.user)["affiliations"]

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
