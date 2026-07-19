"""숙소·호실 시리얼라이저."""

from __future__ import annotations

from rest_framework import serializers

from retreat.models import Lodging, LodgingRoom


class LodgingRoomAssigneeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    group_id = serializers.IntegerField()
    group_name = serializers.CharField()
    gender = serializers.CharField()


class LodgingRoomSerializer(serializers.ModelSerializer):
    recommended_gender_display = serializers.CharField(
        source="get_recommended_gender_display", read_only=True
    )
    label = serializers.CharField(read_only=True)
    lodging_name = serializers.CharField(source="lodging.name", read_only=True)
    region_name = serializers.CharField(source="region.name", read_only=True)
    division_name = serializers.CharField(source="division.name", read_only=True)
    assigned_count = serializers.SerializerMethodField()
    assignees = serializers.SerializerMethodField()

    class Meta:
        model = LodgingRoom
        fields = [
            "id",
            "lodging",
            "lodging_name",
            "region",
            "region_name",
            "division",
            "division_name",
            "number",
            "capacity",
            "recommended_gender",
            "recommended_gender_display",
            "memo",
            "sort_order",
            "label",
            "assigned_count",
            "assignees",
        ]
        read_only_fields = [
            "id",
            "lodging_name",
            "region_name",
            "division_name",
            "recommended_gender_display",
            "label",
            "assigned_count",
            "assignees",
        ]

    def validate(self, attrs):
        """region 과 division 은 같은 region 아래에 있어야 한다 (소속 검증)."""
        region = (
            attrs.get("region")
            if "region" in attrs
            else getattr(self.instance, "region", None)
        )
        division = (
            attrs.get("division")
            if "division" in attrs
            else getattr(self.instance, "division", None)
        )
        if region and division and division.region_id != region.id:
            raise serializers.ValidationError(
                {"division": "선택한 지역에 속한 부서가 아닙니다."}
            )
        return super().validate(attrs)

    def _attendees(self, room: LodgingRoom):
        manager = getattr(room, "attendees", None)
        if manager is None:
            return []
        qs = manager.select_related("group").order_by("name", "id")
        return list(qs)

    def get_assigned_count(self, room: LodgingRoom) -> int:
        return len(self._attendees(room))

    def get_assignees(self, room: LodgingRoom):
        rows = []
        for a in self._attendees(room):
            rows.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "group_id": a.group_id,
                    "group_name": getattr(a.group, "name", "") or "",
                    "gender": a.gender,
                }
            )
        return rows


class LodgingSerializer(serializers.ModelSerializer):
    rooms = LodgingRoomSerializer(many=True, read_only=True)
    region_name = serializers.CharField(source="region.name", read_only=True)

    class Meta:
        model = Lodging
        fields = [
            "id",
            "event",
            "region",
            "region_name",
            "name",
            "address",
            "memo",
            "sort_order",
            "rooms",
        ]
        read_only_fields = ["id", "event", "rooms", "region_name"]
