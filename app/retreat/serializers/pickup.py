from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from retreat.models import RetreatAttendee, RetreatPickup, RetreatPickupLocation


class RetreatPickupSerializer(serializers.ModelSerializer):
    direction_display = serializers.CharField(
        source="get_direction_display", read_only=True
    )
    train_time_display = serializers.SerializerMethodField()
    train_time_input = serializers.SerializerMethodField()
    region_name = serializers.SerializerMethodField()
    division_name = serializers.SerializerMethodField()
    group_name = serializers.SerializerMethodField()
    check_in_status = serializers.SerializerMethodField()
    check_in_status_display = serializers.SerializerMethodField()

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
            "check_in_status",
            "check_in_status_display",
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

    def _matched_attendee(self, obj):
        """픽업 대상(조 + 이름)과 일치하는 조원."""
        if not obj.group_id:
            return None
        if not hasattr(obj, "_matched_attendee_cache"):
            obj._matched_attendee_cache = (
                RetreatAttendee.objects.filter(group_id=obj.group_id, name=obj.name)
                .order_by("id")
                .first()
            )
        return obj._matched_attendee_cache

    def get_check_in_status(self, obj) -> str:
        att = self._matched_attendee(obj)
        return att.check_in_status if att else ""

    def get_check_in_status_display(self, obj) -> str:
        att = self._matched_attendee(obj)
        return att.get_check_in_status_display() if att else ""


class RetreatPickupLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetreatPickupLocation
        fields = [
            "id",
            "event",
            "name",
            "sort_order",
            "created_at",
        ]
        read_only_fields = ["id", "event", "created_at"]
