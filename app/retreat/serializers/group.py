from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatGroup, RetreatGroupMembership, RetreatGroupScope


class RetreatGroupMembershipSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = RetreatGroupMembership
        fields = [
            "id",
            "user",
            "username",
            "display_name",
            "name",
            "role",
            "role_display",
        ]

    def _display_name(self, obj) -> str:
        profile = getattr(obj.user, "profile", None)
        return (getattr(profile, "display_name", "") or "").strip()

    def get_display_name(self, obj) -> str:
        return self._display_name(obj)

    def get_name(self, obj) -> str:
        return self._display_name(obj) or obj.user.username


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
