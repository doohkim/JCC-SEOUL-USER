from __future__ import annotations

from rest_framework import serializers

from registry.models import (
    Member,
    MemberFamilyMember,
    MemberProfile,
    MemberVisitLog,
)


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = [
            "id",
            "name",
            "name_alias",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MemberProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberProfile
        fields = [
            "member",
            "birth_date",
            "phone",
            "address",
            "church_position_display",
            "workplace_display",
            "photo",
            "family_photo",
            "staff_notes",
            "updated_at",
        ]
        read_only_fields = ["member", "updated_at"]


class MemberFamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberFamilyMember
        fields = [
            "id",
            "member",
            "name",
            "relationship",
            "relationship_note",
            "affiliation_text",
            "division",
            "church_position",
            "remarks",
            "sort_order",
        ]
        read_only_fields = ["id", "member"]


class MemberVisitLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberVisitLog
        fields = [
            "id",
            "member",
            "visit_date",
            "contact_method",
            "content",
            "recorded_by",
            "created_at",
        ]
        read_only_fields = ["id", "member", "recorded_by", "created_at"]

