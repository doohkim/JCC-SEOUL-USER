from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from retreat.models import RetreatCouncilMembership, RetreatStaffApplication
from users.services.user_display import user_display_name

User = get_user_model()


class RetreatStaffApplicationSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_display_name = serializers.SerializerMethodField()
    region_name = serializers.CharField(source="region.name", read_only=True)
    division_name = serializers.CharField(source="division.name", read_only=True)
    group_name = serializers.CharField(
        source="group.name", read_only=True, default=""
    )
    group_role_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_pastoral = serializers.SerializerMethodField()
    suggested_council_role = serializers.SerializerMethodField()

    class Meta:
        model = RetreatStaffApplication
        fields = [
            "id",
            "event",
            "user",
            "user_username",
            "user_display_name",
            "region",
            "region_name",
            "division",
            "division_name",
            "group",
            "group_name",
            "group_role",
            "group_role_display",
            "status",
            "status_display",
            "note",
            "rejection_reason",
            "approved_council_role",
            "is_pastoral",
            "suggested_council_role",
            "created_at",
            "reviewed_at",
        ]
        read_only_fields = fields

    def get_user_display_name(self, obj: RetreatStaffApplication) -> str:
        profile = getattr(obj.user, "profile", None)
        if profile and getattr(profile, "real_name", ""):
            return profile.real_name
        return user_display_name(obj.user) or obj.user.username

    def get_group_role_display(self, obj: RetreatStaffApplication) -> str:
        if not obj.group_role:
            return ""
        return dict(obj._meta.get_field("group_role").choices).get(
            obj.group_role, obj.group_role
        )

    def get_is_pastoral(self, obj: RetreatStaffApplication) -> bool:
        from retreat.services.staff_application import is_pastoral_staff_applicant

        return is_pastoral_staff_applicant(obj.user)

    def get_suggested_council_role(self, obj: RetreatStaffApplication) -> str:
        from retreat.services.staff_application import suggest_council_role

        if not self.get_is_pastoral(obj):
            return ""
        return suggest_council_role(obj)


class RetreatStaffApplicationReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    council_role = serializers.ChoiceField(
        choices=RetreatCouncilMembership.Role.choices,
        required=False,
        allow_blank=True,
    )
    rejection_reason = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )
