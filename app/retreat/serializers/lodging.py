"""숙소·호실 시리얼라이저."""

from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from retreat.models import (
    Lodging,
    LodgingRoom,
    LodgingRoomGroupTarget,
    LodgingRoomScope,
    RetreatGroup,
)
from users.models import Division


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
    scope_divisions = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        write_only=True,
    )
    target_groups = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        write_only=True,
    )
    scopes = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()

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
            "scope_divisions",
            "target_groups",
            "scopes",
            "groups",
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
            "scopes",
            "groups",
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
        gender = attrs.get(
            "recommended_gender",
            getattr(self.instance, "recommended_gender", ""),
        )
        if self.instance is None and gender not in (
            LodgingRoom.Gender.MALE,
            LodgingRoom.Gender.FEMALE,
        ):
            raise serializers.ValidationError(
                {"recommended_gender": "호실 성별을 선택하세요."}
            )
        if "recommended_gender" in attrs and gender not in (
            LodgingRoom.Gender.MALE,
            LodgingRoom.Gender.FEMALE,
        ):
            raise serializers.ValidationError(
                {"recommended_gender": "남성 또는 여성만 선택할 수 있습니다."}
            )
        if "scope_divisions" not in attrs and (
            "region" in attrs or "division" in attrs
        ):
            # 구 API의 단일 region/division PATCH도 새 다중 범위와 동기화한다.
            attrs["scope_divisions"] = [division.id] if region and division else []

        division_ids = list(dict.fromkeys(attrs.get("scope_divisions", [])))
        group_ids = list(dict.fromkeys(attrs.get("target_groups", [])))

        found_divisions = list(
            Division.objects.select_related("region").filter(id__in=division_ids)
        )
        if len(found_divisions) != len(division_ids):
            raise serializers.ValidationError(
                {"scope_divisions": "존재하지 않는 부서가 포함되어 있습니다."}
            )
        division_map = {division.id: division for division in found_divisions}
        divisions = [division_map[division_id] for division_id in division_ids]

        lodging = attrs.get("lodging") or getattr(self.instance, "lodging", None)
        found_groups = list(RetreatGroup.objects.filter(id__in=group_ids))
        if len(found_groups) != len(group_ids):
            raise serializers.ValidationError(
                {"target_groups": "존재하지 않는 조가 포함되어 있습니다."}
            )
        group_map = {group.id: group for group in found_groups}
        groups = [group_map[group_id] for group_id in group_ids]
        if lodging and any(group.event_id != lodging.event_id for group in groups):
            raise serializers.ValidationError(
                {"target_groups": "같은 집회의 조만 선택할 수 있습니다."}
            )

        attrs["_scope_division_objects"] = divisions
        attrs["_target_group_objects"] = groups
        return super().validate(attrs)

    def _pop_targets(self, validated_data):
        scope_was_sent = "scope_divisions" in validated_data
        groups_were_sent = "target_groups" in validated_data
        validated_data.pop("scope_divisions", None)
        validated_data.pop("target_groups", None)
        divisions = validated_data.pop("_scope_division_objects", [])
        groups = validated_data.pop("_target_group_objects", [])
        return scope_was_sent, groups_were_sent, divisions, groups

    def _sync_targets(
        self,
        room,
        *,
        scope_was_sent,
        groups_were_sent,
        divisions,
        groups,
    ):
        if scope_was_sent:
            room.scopes.all().delete()
            LodgingRoomScope.objects.bulk_create(
                [
                    LodgingRoomScope(room=room, division=division)
                    for division in divisions
                ]
            )
            primary = divisions[0] if divisions else None
            room.region = primary.region if primary else None
            room.division = primary
            room.save(update_fields=["region", "division"])
        if groups_were_sent:
            room.group_targets.all().delete()
            LodgingRoomGroupTarget.objects.bulk_create(
                [LodgingRoomGroupTarget(room=room, group=group) for group in groups]
            )

    @transaction.atomic
    def create(self, validated_data):
        target_data = self._pop_targets(validated_data)
        room = super().create(validated_data)
        self._sync_targets(
            room,
            scope_was_sent=target_data[0],
            groups_were_sent=target_data[1],
            divisions=target_data[2],
            groups=target_data[3],
        )
        return room

    @transaction.atomic
    def update(self, instance, validated_data):
        target_data = self._pop_targets(validated_data)
        room = super().update(instance, validated_data)
        self._sync_targets(
            room,
            scope_was_sent=target_data[0],
            groups_were_sent=target_data[1],
            divisions=target_data[2],
            groups=target_data[3],
        )
        return room

    def get_scopes(self, room: LodgingRoom):
        scopes = list(room.scopes.select_related("division__region").all())
        if not scopes and room.region_id and room.division_id:
            return [
                {
                    "division_id": room.division_id,
                    "region_name": room.region.name,
                    "division_name": room.division.name,
                }
            ]
        return [
            {
                "division_id": scope.division_id,
                "region_name": scope.division.region.name,
                "division_name": scope.division.name,
            }
            for scope in scopes
        ]

    def get_groups(self, room: LodgingRoom):
        return [
            {"id": target.group_id, "name": target.group.name}
            for target in room.group_targets.select_related("group").all()
        ]

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
