from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from retreat.models import RetreatPickup


class RetreatPickupSerializer(serializers.ModelSerializer):
    direction_display = serializers.CharField(
        source="get_direction_display", read_only=True
    )
    train_time_display = serializers.SerializerMethodField()
    train_time_input = serializers.SerializerMethodField()
    region_name = serializers.SerializerMethodField()
    division_name = serializers.SerializerMethodField()
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = RetreatPickup
        fields = [
            "id",
            "direction",
            "direction_display",
            "number",
            "group",
            "group_name",
            "name",
            "region",
            "region_name",
            "division",
            "division_name",
            "train_time",
            "train_time_display",
            "train_time_input",
            "boarding_place",
            "contact",
            "note",
            "applicant_name",
            "created_at",
        ]
        read_only_fields = ["id", "number", "applicant_name", "created_at"]

    def get_train_time_display(self, obj) -> str:
        if not obj.train_time:
            return ""
        return timezone.localtime(obj.train_time).strftime("%Y-%m-%d %H:%M")

    def get_train_time_input(self, obj) -> str:
        """datetime-local 입력 프리필용 (YYYY-MM-DDTHH:MM, 로컬시간)."""
        if not obj.train_time:
            return ""
        return timezone.localtime(obj.train_time).strftime("%Y-%m-%dT%H:%M")

    def get_region_name(self, obj) -> str:
        return obj.region.name if obj.region_id else ""

    def get_division_name(self, obj) -> str:
        return obj.division.name if obj.division_id else ""

    def get_group_name(self, obj) -> str:
        return obj.group.name if obj.group_id else ""
