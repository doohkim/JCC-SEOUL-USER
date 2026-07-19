from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from retreat.models import (
    RetreatCouncilMembership,
    RetreatGroupMembership,
    RetreatStaffApplication,
)
from users.services.user_display import user_display_name

User = get_user_model()


class RetreatStaffApplicationSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_display_name = serializers.SerializerMethodField()
    region_name = serializers.CharField(source="region.name", read_only=True)
    division_name = serializers.CharField(source="division.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True, default="")
    group_role_display = serializers.SerializerMethodField()
    application_track_display = serializers.SerializerMethodField()
    is_council_track = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_pastoral = serializers.SerializerMethodField()
    approved_council_role_display = serializers.SerializerMethodField()
    suggested_council_role = serializers.SerializerMethodField()
    eligible_groups = serializers.SerializerMethodField()

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
            "application_track",
            "application_track_display",
            "is_council_track",
            "group",
            "group_name",
            "group_role",
            "group_role_display",
            "status",
            "status_display",
            "rejection_reason",
            "approved_council_role",
            "approved_council_role_display",
            "is_pastoral",
            "suggested_council_role",
            "eligible_groups",
            "created_at",
            "reviewed_at",
        ]
        read_only_fields = fields

    def get_approved_council_role_display(self, obj: RetreatStaffApplication) -> str:
        if not obj.approved_council_role:
            return ""
        return dict(RetreatCouncilMembership.Role.choices).get(
            obj.approved_council_role, obj.approved_council_role
        )

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

    def get_application_track_display(self, obj: RetreatStaffApplication) -> str:
        if not obj.application_track:
            return ""
        return dict(obj._meta.get_field("application_track").choices).get(
            obj.application_track, obj.application_track
        )

    def get_is_council_track(self, obj: RetreatStaffApplication) -> bool:
        from retreat.services.staff_application import is_council_track_application

        return is_council_track_application(obj)

    def get_is_pastoral(self, obj: RetreatStaffApplication) -> bool:
        from retreat.services.staff_application import is_pastoral_staff_applicant

        return is_pastoral_staff_applicant(obj.user)

    def get_suggested_council_role(self, obj: RetreatStaffApplication) -> str:
        from retreat.services.staff_application import (
            is_council_track_application,
            suggest_council_role,
        )

        if not is_council_track_application(obj):
            return ""
        return suggest_council_role(obj)

    def get_eligible_groups(self, obj: RetreatStaffApplication) -> list[dict]:
        from retreat.services.staff_application import (
            eligible_groups_payload_for_member,
            is_pastoral_staff_applicant,
        )

        if obj.status != RetreatStaffApplication.Status.PENDING:
            return []
        if is_pastoral_staff_applicant(obj.user):
            return []
        return eligible_groups_payload_for_member(obj.user, obj.event)


class RetreatStaffApplicationReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    council_role = serializers.ChoiceField(
        choices=RetreatCouncilMembership.Role.choices,
        required=False,
        allow_blank=True,
    )
    group_id = serializers.IntegerField(required=False, allow_null=True)
    group_role = serializers.ChoiceField(
        choices=RetreatGroupMembership.Role.choices,
        required=False,
        allow_blank=True,
    )
    rejection_reason = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )
