from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatChangeLog


class RetreatChangeLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    target_type_display = serializers.CharField(
        source="get_target_type_display", read_only=True
    )

    class Meta:
        model = RetreatChangeLog
        fields = [
            "id",
            "action",
            "action_display",
            "target_type",
            "target_type_display",
            "target_id",
            "payload_before",
            "payload_after",
            "changed_by",
            "changed_by_name",
            "changed_at",
        ]

    def get_changed_by_name(self, obj) -> str:
        if obj.changed_by_id and obj.changed_by:
            return obj.changed_by.get_username()
        return ""
