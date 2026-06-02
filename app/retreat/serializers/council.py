from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from retreat.models import RetreatCouncilMembership

User = get_user_model()


class RetreatCouncilMembershipSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = RetreatCouncilMembership
        fields = [
            "id",
            "user",
            "user_username",
            "role",
            "role_display",
            "note",
            "created_at",
        ]
