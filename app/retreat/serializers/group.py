from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatGroup, RetreatGroupMembership, RetreatGroupScope
from retreat.services.account_retired import ACCOUNT_RETIRED_DISPLAY, is_retired_user
from retreat.services.group_sync import home_group_meta_for_user
from users.services.user_display import user_account_link_label


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


class RetreatGroupMembershipSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    user_real_name = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    user_region_id = serializers.SerializerMethodField()
    user_division_id = serializers.SerializerMethodField()
    user_affiliations = serializers.SerializerMethodField()
    user_account_retired = serializers.SerializerMethodField()
    user_account_retired_display = serializers.SerializerMethodField()
    home_group_id = serializers.SerializerMethodField()
    home_group_name = serializers.SerializerMethodField()
    is_cross_group_leader = serializers.SerializerMethodField()

    class Meta:
        model = RetreatGroupMembership
        fields = [
            "id",
            "user",
            "username",
            "display_name",
            "name",
            "user_real_name",
            "user_phone",
            "user_region_id",
            "user_division_id",
            "user_affiliations",
            "user_account_retired",
            "user_account_retired_display",
            "home_group_id",
            "home_group_name",
            "is_cross_group_leader",
            "role",
            "role_display",
            "created_at",
        ]

    def _home_meta(self, obj) -> dict:
        cache = getattr(self, "_home_meta_cache", None)
        if cache is None:
            cache = {}
            self._home_meta_cache = cache
        key = (obj.user_id, obj.group.event_id, obj.group_id)
        if key not in cache:
            cache[key] = home_group_meta_for_user(
                user=obj.user,
                event_id=obj.group.event_id,
                assigned_group_id=obj.group_id,
            )
        return cache[key]

    def get_home_group_id(self, obj) -> int | None:
        return self._home_meta(obj)["home_group_id"]

    def get_home_group_name(self, obj) -> str:
        return self._home_meta(obj)["home_group_name"]

    def get_is_cross_group_leader(self, obj) -> bool:
        return self._home_meta(obj)["is_cross_group_leader"]

    def _affiliation_bundle(self, user) -> dict:
        cache = getattr(self, "_user_affiliation_cache", None)
        if cache is None:
            cache = {}
            self._user_affiliation_cache = cache
        key = user.id
        if key in cache:
            return cache[key]

        seen: set[int] = set()
        affiliations: list[dict] = []
        primary_region_id = None
        primary_division_id = None
        for row in _division_team_rows_for(user):
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

    def _display_name(self, obj) -> str:
        return user_account_link_label(obj.user)

    def get_display_name(self, obj) -> str:
        return self._display_name(obj)

    def get_name(self, obj) -> str:
        label = self._display_name(obj)
        return label if label != obj.user.username else obj.user.username

    def get_user_real_name(self, obj) -> str:
        profile = getattr(obj.user, "profile", None)
        return (getattr(profile, "real_name", "") or "").strip()

    def get_user_phone(self, obj) -> str:
        profile = getattr(obj.user, "profile", None)
        return (getattr(profile, "phone", "") or "").strip()

    def get_user_region_id(self, obj) -> int | None:
        return self._affiliation_bundle(obj.user)["region_id"]

    def get_user_division_id(self, obj) -> int | None:
        return self._affiliation_bundle(obj.user)["division_id"]

    def get_user_affiliations(self, obj) -> list[dict]:
        return self._affiliation_bundle(obj.user)["affiliations"]

    def get_user_account_retired(self, obj) -> bool:
        return is_retired_user(obj.user)

    def get_user_account_retired_display(self, obj) -> str:
        return ACCOUNT_RETIRED_DISPLAY if is_retired_user(obj.user) else ""


class RetreatGroupScopeSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True)
    division_name = serializers.CharField(source="division.name", read_only=True)

    class Meta:
        model = RetreatGroupScope
        fields = ["id", "region", "region_name", "division", "division_name"]


class RetreatGroupSerializer(serializers.ModelSerializer):
    region_code = serializers.CharField(source="region.code", read_only=True)
    region_name = serializers.CharField(source="region.name", read_only=True)
    division_code = serializers.CharField(source="division.code", read_only=True)
    division_name = serializers.CharField(source="division.name", read_only=True)
    attendee_count = serializers.IntegerField(read_only=True, default=0)
    memberships = RetreatGroupMembershipSerializer(many=True, read_only=True)
    extra_scopes = RetreatGroupScopeSerializer(many=True, read_only=True)

    class Meta:
        model = RetreatGroup
        fields = [
            "id",
            "event",
            "region",
            "region_code",
            "region_name",
            "division",
            "division_code",
            "division_name",
            "name",
            "order",
            "attendee_count",
            "memberships",
            "extra_scopes",
        ]
