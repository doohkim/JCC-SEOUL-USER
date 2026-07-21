from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatGroup, RetreatGroupMembership, RetreatGroupScope
from retreat.services.account_retired import ACCOUNT_RETIRED_DISPLAY, is_retired_user
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
    user_account_retired = serializers.SerializerMethodField()
    user_account_retired_display = serializers.SerializerMethodField()

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
            "user_account_retired",
            "user_account_retired_display",
            "role",
            "role_display",
            "created_at",
        ]

    def _affiliation_ids(self, user) -> tuple[int | None, int | None]:
        cache = getattr(self, "_user_affiliation_id_cache", None)
        if cache is None:
            cache = {}
            self._user_affiliation_id_cache = cache
        key = user.id
        if key in cache:
            return cache[key]

        region_id = None
        division_id = None
        for row in _division_team_rows_for(user):
            division = getattr(row, "division", None)
            if not division or not row.division_id:
                continue
            division_id = row.division_id
            region_id = division.region_id
            break
        cache[key] = (region_id, division_id)
        return cache[key]

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
        region_id, _division_id = self._affiliation_ids(obj.user)
        return region_id

    def get_user_division_id(self, obj) -> int | None:
        _region_id, division_id = self._affiliation_ids(obj.user)
        return division_id

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
