"""집회 운영진 명단 관리 API."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import (
    RetreatChangeLog,
    RetreatCouncilMembership,
    RetreatEvent,
)
from retreat.serializers import RetreatCouncilMembershipSerializer
from retreat.services.account_retired import (
    assert_user_visible_to,
    visible_user_linked_for,
)
from retreat.services.audit import log_retreat_change
from retreat.services.staff_roster import (
    CouncilScopeError,
    assert_can_assign_event_staff,
    resolve_council_staff_scope,
)
from retreat.services.staff_pool import event_staff_eligible_division_ids
from users.permissions import (
    can_access_retreat_admin,
    can_access_retreat_tab,
    can_manage_staff,
)
from users.models import UserDivisionTeam

User = get_user_model()


def _assert_event_access(user) -> None:
    if not can_access_retreat_tab(user):
        raise PermissionDenied


def _assert_can_view(user, event: RetreatEvent) -> None:
    _assert_event_access(user)
    if not (user.is_superuser or can_access_retreat_admin(user, event)):
        raise PermissionDenied("집회 운영진 명단 조회 권한이 없습니다.")


def _assert_can_manage(user, event: RetreatEvent) -> None:
    _assert_event_access(user)
    if not can_manage_staff(user, event):
        raise PermissionDenied("집회 운영진 등록·삭제는 집회 전체 관리자만 가능합니다.")


def _validate_staff_scope(
    role: str,
    *,
    region_id: int | None,
    division_id: int | None,
) -> tuple[int | None, int | None]:
    try:
        return resolve_council_staff_scope(
            role, region_id=region_id, division_id=division_id
        )
    except CouncilScopeError as exc:
        raise ValidationError({exc.field: str(exc)}) from exc


def _candidate_affiliations_for_staff_scope(user):
    rows = (
        user.division_teams.order_by(
            "-is_primary",
            "sort_order",
            "division__sort_order",
            "id",
        )
        .select_related("division", "division__region")
        .all()
    )
    values = [
        (
            row.division_id,
            row.division.region_id if row.division else None,
        )
        for row in rows
        if row.division_id
    ]
    seen = set()
    results = []
    for division_id, region_id in values:
        if division_id in seen:
            continue
        seen.add(division_id)
        results.append((division_id, region_id))
    return results


def _validate_user_scope_intersection(
    *,
    event: RetreatEvent,
    user,
    role: str,
    region_id: int | None,
    division_id: int | None,
) -> None:
    if role in RetreatCouncilMembership.EVENT_WIDE_ROLES:
        return
    event_division_ids = event_staff_eligible_division_ids(event.id)
    if not event_division_ids:
        raise ValidationError(
            {
                "scope": "집회에 배정된 부서가 없어 역할을 저장할 수 없습니다. 집회 조/범위를 먼저 확인해 주세요."
            }
        )
    scoped = [
        (d_id, r_id)
        for d_id, r_id in _candidate_affiliations_for_staff_scope(user)
        if d_id in event_division_ids
    ]
    if not scoped:
        raise ValidationError(
            {
                "scope": "이 사용자는 이 집회의 배정 부서와 겹치는 담당 부서가 없어 역할을 저장할 수 없습니다. 사용자 소속 또는 집회 배정 부서를 확인해 주세요."
            }
        )
    if role in RetreatCouncilMembership.DIVISION_SCOPED_ROLES:
        allowed_division_ids = {d_id for d_id, _ in scoped}
        if not division_id or division_id not in allowed_division_ids:
            raise ValidationError(
                {
                    "division": "선택한 담당 부서는 이 사용자의 담당 부서(집회 배정 부서 교집합)에 없습니다."
                }
            )
    if role in RetreatCouncilMembership.REGION_SCOPED_ROLES:
        allowed_region_ids = {r_id for _, r_id in scoped if r_id}
        if not region_id or region_id not in allowed_region_ids:
            raise ValidationError(
                {
                    "region": "선택한 담당 지역은 이 사용자의 담당 부서(집회 배정 부서 교집합)에서 선택할 수 없습니다."
                }
            )


class RetreatEventCouncilListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_view(request.user, event)
        qs = (
            event.council_memberships.select_related(
                "user", "user__profile", "user__role_level", "region", "division"
            )
            .prefetch_related(
                Prefetch(
                    "user__division_teams",
                    queryset=UserDivisionTeam.objects.select_related(
                        "division", "division__region"
                    ).order_by(
                        "-is_primary",
                        "sort_order",
                        "division__sort_order",
                        "id",
                    ),
                    to_attr="prefetched_division_teams",
                )
            )
            .order_by("role", "user__username")
        )
        qs = visible_user_linked_for(request.user, qs, user_prefix="user")
        return Response(RetreatCouncilMembershipSerializer(qs, many=True).data)

    def post(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_manage(request.user, event)
        username = (request.data.get("username") or "").strip()
        user_id = request.data.get("user_id")
        role = (
            request.data.get("role") or RetreatCouncilMembership.Role.EVENT_ADMIN
        ).strip()
        note = (request.data.get("note") or "").strip()
        if role not in dict(RetreatCouncilMembership.Role.choices):
            raise ValidationError({"role": "올바르지 않은 역할입니다."})
        region_id = request.data.get("region") or request.data.get("region_id")
        division_id = request.data.get("division") or request.data.get("division_id")
        region_id = int(region_id) if region_id else None
        division_id = int(division_id) if division_id else None
        region_id, division_id = _validate_staff_scope(
            role, region_id=region_id, division_id=division_id
        )
        target = None
        if user_id:
            target = User.objects.filter(pk=user_id).first()
        elif username:
            target = User.objects.filter(username=username).first()
        if target is None:
            raise ValidationError({"user": "사용자를 찾을 수 없습니다."})
        _validate_user_scope_intersection(
            event=event,
            user=target,
            role=role,
            region_id=region_id,
            division_id=division_id,
        )
        if not RetreatCouncilMembership.objects.filter(
            event=event, user=target
        ).exists():
            try:
                assert_can_assign_event_staff(target, event, kind="council")
            except ValueError as exc:
                raise ValidationError({"user": str(exc)}) from exc
        existing = RetreatCouncilMembership.objects.filter(
            event=event, user=target
        ).first()
        payload_before = (
            {
                "staff": True,
                "user_id": target.id,
                "role": existing.role,
                "region_id": existing.region_id,
                "division_id": existing.division_id,
                "note": existing.note,
            }
            if existing
            else None
        )
        membership, created = RetreatCouncilMembership.objects.update_or_create(
            event=event,
            user=target,
            defaults={
                "role": role,
                "note": note,
                "region_id": region_id,
                "division_id": division_id,
            },
        )
        if created:
            membership.created_by = request.user
            membership.save(update_fields=["created_by"])
        log_retreat_change(
            user=request.user,
            event=event,
            action=(
                RetreatChangeLog.Action.CREATE
                if created
                else RetreatChangeLog.Action.UPDATE
            ),
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=membership.id,
            payload_before=payload_before,
            payload_after={
                "staff": True,
                "user_id": target.id,
                "role": role,
                "region_id": region_id,
                "division_id": division_id,
                "note": note,
            },
        )
        return Response(
            RetreatCouncilMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RetreatCouncilMembershipDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, event_id: int, membership_id: int) -> RetreatCouncilMembership:
        return get_object_or_404(
            RetreatCouncilMembership.objects.select_related(
                "event", "user", "region", "division"
            ),
            pk=membership_id,
            event_id=event_id,
        )

    def patch(self, request, event_id: int, membership_id: int):
        m = self._get(event_id, membership_id)
        assert_user_visible_to(request.user, m.user)
        _assert_can_manage(request.user, m.event)
        role = (request.data.get("role") or m.role).strip()
        note = request.data.get("note", m.note)
        if role not in dict(RetreatCouncilMembership.Role.choices):
            raise ValidationError({"role": "올바르지 않은 역할입니다."})
        region_id = request.data.get("region", m.region_id)
        division_id = request.data.get("division", m.division_id)
        if "region_id" in request.data:
            region_id = request.data.get("region_id")
        if "division_id" in request.data:
            division_id = request.data.get("division_id")
        region_id = int(region_id) if region_id else None
        division_id = int(division_id) if division_id else None
        region_id, division_id = _validate_staff_scope(
            role, region_id=region_id, division_id=division_id
        )
        _validate_user_scope_intersection(
            event=m.event,
            user=m.user,
            role=role,
            region_id=region_id,
            division_id=division_id,
        )
        before = {
            "staff": True,
            "user_id": m.user_id,
            "role": m.role,
            "region_id": m.region_id,
            "division_id": m.division_id,
            "note": m.note,
        }
        m.role = role
        m.note = note
        m.region_id = region_id
        m.division_id = division_id
        m.save(update_fields=["role", "note", "region_id", "division_id"])
        log_retreat_change(
            user=request.user,
            event=m.event,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=m.id,
            payload_before=before,
            payload_after={
                "staff": True,
                "user_id": m.user_id,
                "role": role,
                "region_id": region_id,
                "division_id": division_id,
                "note": note,
            },
        )
        return Response(RetreatCouncilMembershipSerializer(m).data)

    def delete(self, request, event_id: int, membership_id: int):
        m = self._get(event_id, membership_id)
        assert_user_visible_to(request.user, m.user)
        _assert_can_manage(request.user, m.event)
        before = {
            "staff": True,
            "user_id": m.user_id,
            "role": m.role,
            "region_id": m.region_id,
            "division_id": m.division_id,
        }
        event = m.event
        user = m.user
        mid = m.id
        m.delete()
        from retreat.services.staff_application import (
            delete_staff_application_if_unassigned,
        )

        delete_staff_application_if_unassigned(user, event, actor=request.user)
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=mid,
            payload_before=before,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
