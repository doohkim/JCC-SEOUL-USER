"""행사·그룹 목록 API."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.apis._common import assert_can_add_group, get_group_or_403
from retreat.models import (
    RetreatChangeLog,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatGroupScope,
)
from retreat.serializers import RetreatEventSerializer, RetreatGroupSerializer
from retreat.services.audit import log_retreat_change
from users.models import Division
from users.permissions import visible_retreat_groups_for

User = get_user_model()


def _serialize_group(group: RetreatGroup) -> dict:
    return RetreatGroupSerializer(
        RetreatGroup.objects.filter(pk=group.pk)
        .select_related("region", "division")
        .prefetch_related("memberships__user", "extra_scopes__region", "extra_scopes__division")
        .annotate(attendee_count=Count("attendees", distinct=True))
        .first()
    ).data


def _parse_extra_scopes(
    data: dict,
    *,
    primary_region_id: int,
    primary_division_id: int,
) -> list[tuple[int, int]]:
    """보조 (지역, 부서) 쌍 검증. 대표와 중복·보조 간 중복 불가."""
    scopes = data.get("scopes")
    if scopes is None:
        return []
    if not isinstance(scopes, list):
        raise ValidationError({"scopes": "보조 지역·부서 형식이 올바르지 않습니다."})

    seen = {(int(primary_region_id), int(primary_division_id))}
    parsed: list[tuple[int, int]] = []
    for idx, item in enumerate(scopes, start=1):
        if not isinstance(item, dict):
            raise ValidationError(
                {"scopes": f"{idx}번째 보조 범위: 형식이 올바르지 않습니다."}
            )
        region_id = item.get("region")
        division_id = item.get("division")
        if not region_id or not division_id:
            raise ValidationError(
                {"scopes": f"{idx}번째 보조 범위: 지역과 부서를 선택하세요."}
            )
        division = get_object_or_404(
            Division.objects.select_related("region"), pk=int(division_id)
        )
        if int(region_id) != division.region_id:
            raise ValidationError(
                {
                    "scopes": (
                        f"{idx}번째 보조 범위: 선택한 지역에 속한 부서가 아닙니다."
                    )
                }
            )
        pair = (int(region_id), int(division_id))
        if pair in seen:
            raise ValidationError(
                {"scopes": f"{idx}번째 보조 범위: 중복된 지역·부서입니다."}
            )
        seen.add(pair)
        parsed.append(pair)
    return parsed


def _create_single_group(
    event: RetreatEvent,
    user,
    data: dict,
    *,
    reserved_names: set[str] | None = None,
) -> RetreatGroup:
    """행사에 조 1개 생성. reserved_names에 같은 요청 배치 내 이름 중복 검사."""
    region_id = data.get("region")
    division_id = data.get("division")
    name = (data.get("name") or "").strip()
    order = data.get("order", 0)
    leaders = data.get("leaders") or []

    if not name:
        raise ValidationError({"name": "조 이름은 필수입니다."})
    if not region_id or not division_id:
        raise ValidationError({"region": "지역과 부서를 선택하세요."})

    division = get_object_or_404(
        Division.objects.select_related("region"), pk=int(division_id)
    )
    if int(region_id) != division.region_id:
        raise ValidationError(
            {"division": "선택한 지역에 속한 부서가 아닙니다."}
        )

    extra_scope_pairs = _parse_extra_scopes(
        data,
        primary_region_id=int(region_id),
        primary_division_id=int(division_id),
    )

    if reserved_names is not None and name in reserved_names:
        raise ValidationError({"name": "같은 요청에 중복된 조 이름이 있습니다."})

    if RetreatGroup.objects.filter(event=event, name=name).exists():
        raise ValidationError(
            {"name": "이 행사에 이미 같은 이름의 조가 있습니다."}
        )

    if reserved_names is not None:
        reserved_names.add(name)

    group = RetreatGroup.objects.create(
        event=event,
        region_id=int(region_id),
        division=division,
        name=name,
        order=int(order or 0),
    )
    for region_id, division_id in extra_scope_pairs:
        RetreatGroupScope.objects.create(
            group=group,
            region_id=region_id,
            division_id=division_id,
        )

    log_retreat_change(
        user=user,
        event=event,
        action=RetreatChangeLog.Action.CREATE,
        target_type=RetreatChangeLog.TargetType.GROUP,
        target_id=group.id,
        payload_after={
            "event_id": event.id,
            "region_id": group.region_id,
            "division_id": group.division_id,
            "name": group.name,
            "order": group.order,
            "extra_scopes": [
                {"region_id": rid, "division_id": did}
                for rid, did in extra_scope_pairs
            ],
        },
    )

    for entry in leaders:
        if not isinstance(entry, dict):
            continue
        user_id = entry.get("user_id")
        role = (entry.get("role") or RetreatGroupMembership.Role.LEADER).strip()
        if role not in dict(RetreatGroupMembership.Role.choices):
            continue
        if not user_id:
            continue
        target = User.objects.filter(pk=user_id, is_active=True).first()
        if target is None:
            continue
        membership, created = RetreatGroupMembership.objects.update_or_create(
            group=group,
            user=target,
            defaults={"role": role},
        )
        log_retreat_change(
            user=user,
            event=event,
            action=RetreatChangeLog.Action.CREATE
            if created
            else RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=membership.id,
            payload_after={
                "group_id": group.id,
                "user_id": target.id,
                "role": role,
            },
        )

    return group


class RetreatEventListView(APIView):
    """현재 사용자에게 노출 가능한 활성 행사 목록.

    - 활성 행사 중, 본인이 1개 이상 그룹을 볼 수 있거나 슈퍼유저인 행사만.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        events = RetreatEvent.objects.filter(is_active=True).prefetch_related("sessions")
        if not request.user.is_superuser:
            visible = []
            for ev in events:
                if visible_retreat_groups_for(request.user, ev).exists():
                    visible.append(ev)
            events = visible
        return Response(
            RetreatEventSerializer(
                events,
                many=True,
                context={"request": request},
            ).data
        )


class RetreatEventGroupListView(APIView):
    """특정 행사에서 본인이 볼 수 있는 조 목록."""

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        groups = (
            visible_retreat_groups_for(request.user, event)
            .select_related("region", "division")
            .prefetch_related(
                "memberships__user",
                "extra_scopes__region",
                "extra_scopes__division",
            )
            .annotate(attendee_count=Count("attendees", distinct=True))
        )
        return Response(RetreatGroupSerializer(groups, many=True).data)

    def post(self, request, event_id: int):
        """행사에 조 추가 (회장단·슈퍼유저). 단건 또는 groups 일괄."""
        event = get_object_or_404(RetreatEvent, pk=event_id)
        assert_can_add_group(request.user, event)

        bulk = request.data.get("groups")
        if bulk is not None:
            if not isinstance(bulk, list) or not bulk:
                raise ValidationError({"groups": "추가할 조 목록이 비어 있습니다."})
            created: list[RetreatGroup] = []
            reserved_names: set[str] = set()
            try:
                with transaction.atomic():
                    for idx, item in enumerate(bulk, start=1):
                        if not isinstance(item, dict):
                            raise ValidationError(
                                {"detail": f"{idx}번째 조: 형식이 올바르지 않습니다."}
                            )
                        try:
                            group = _create_single_group(
                                event,
                                request.user,
                                item,
                                reserved_names=reserved_names,
                            )
                        except ValidationError as exc:
                            detail = exc.detail
                            if isinstance(detail, dict):
                                first = next(iter(detail.values()))
                                msg = first[0] if isinstance(first, list) else first
                            else:
                                msg = str(detail)
                            raise ValidationError(
                                {"detail": f"{idx}번째 조: {msg}"}
                            ) from exc
                        created.append(group)
            except ValidationError:
                raise
            serialized = [_serialize_group(g) for g in created]
            return Response(serialized, status=status.HTTP_201_CREATED)

        group = _create_single_group(event, request.user, request.data)
        return Response(
            _serialize_group(group),
            status=status.HTTP_201_CREATED,
        )


def _update_group(group: RetreatGroup, user, data: dict) -> RetreatGroup:
    """조 이름·대표·보조 범위·정렬 수정."""
    region_id = data.get("region", group.region_id)
    division_id = data.get("division", group.division_id)
    name = (data.get("name") if "name" in data else group.name) or ""
    name = name.strip()
    order = data.get("order", group.order)

    if not name:
        raise ValidationError({"name": "조 이름은 필수입니다."})
    if not region_id or not division_id:
        raise ValidationError({"region": "지역과 부서를 선택하세요."})

    division = get_object_or_404(
        Division.objects.select_related("region"), pk=int(division_id)
    )
    if int(region_id) != division.region_id:
        raise ValidationError(
            {"division": "선택한 지역에 속한 부서가 아닙니다."}
        )

    extra_scope_pairs: list[tuple[int, int]] | None
    if "scopes" in data:
        extra_scope_pairs = _parse_extra_scopes(
            data,
            primary_region_id=int(region_id),
            primary_division_id=int(division_id),
        )
    else:
        extra_scope_pairs = None

    if (
        RetreatGroup.objects.filter(event=group.event, name=name)
        .exclude(pk=group.pk)
        .exists()
    ):
        raise ValidationError(
            {"name": "이 행사에 이미 같은 이름의 조가 있습니다."}
        )

    before_scopes = list(
        group.extra_scopes.values_list("region_id", "division_id")
    )
    payload_before = {
        "event_id": group.event_id,
        "region_id": group.region_id,
        "division_id": group.division_id,
        "name": group.name,
        "order": group.order,
        "extra_scopes": [
            {"region_id": rid, "division_id": did} for rid, did in before_scopes
        ],
    }

    with transaction.atomic():
        group.name = name
        group.region_id = int(region_id)
        group.division_id = int(division_id)
        group.order = int(order or 0)
        group.save(update_fields=["name", "region_id", "division_id", "order", "updated_at"])

        if extra_scope_pairs is not None:
            group.extra_scopes.all().delete()
            for rid, did in extra_scope_pairs:
                RetreatGroupScope.objects.create(
                    group=group,
                    region_id=rid,
                    division_id=did,
                )

    after_scopes = (
        extra_scope_pairs
        if extra_scope_pairs is not None
        else list(group.extra_scopes.values_list("region_id", "division_id"))
    )
    log_retreat_change(
        user=user,
        event=group.event,
        action=RetreatChangeLog.Action.UPDATE,
        target_type=RetreatChangeLog.TargetType.GROUP,
        target_id=group.id,
        payload_before=payload_before,
        payload_after={
            "event_id": group.event_id,
            "region_id": group.region_id,
            "division_id": group.division_id,
            "name": group.name,
            "order": group.order,
            "extra_scopes": [
                {"region_id": rid, "division_id": did}
                for rid, did in after_scopes
            ],
        },
    )
    return group


class RetreatGroupDetailView(APIView):
    """조 단건 조회·수정 (회장단·슈퍼유저)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id: int):
        group = get_group_or_403(request.user, group_id)
        return Response(_serialize_group(group))

    def patch(self, request, group_id: int):
        group = get_group_or_403(request.user, group_id)
        assert_can_add_group(request.user, group.event)
        group = _update_group(group, request.user, request.data)
        return Response(_serialize_group(group))
