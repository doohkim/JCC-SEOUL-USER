"""수련회 픽업(입회/출회) 정보 API."""

from __future__ import annotations

import re

from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import (
    RetreatChangeLog,
    RetreatEvent,
    RetreatGroup,
    RetreatPickup,
    RetreatPickupLocation,
)
from retreat.serializers import RetreatPickupSerializer
from retreat.services.audit import log_retreat_change
from users.models import Division, Region
from users.permissions import (
    can_access_retreat_tab,
    can_manage_retreat_pickup,
    can_select_pickup_group,
    retreat_pickup_group_ids_for,
)


def _assert_can_view(user, event: RetreatEvent) -> None:
    if not can_access_retreat_tab(user):
        raise PermissionDenied("수련회 화면 접근 권한이 없습니다.")


def _assert_can_manage(user, event: RetreatEvent) -> None:
    _assert_can_view(user, event)
    if not can_manage_retreat_pickup(user, event):
        raise PermissionDenied("픽업 정보 추가·삭제 권한이 없습니다.")


def _parse_direction(value) -> str:
    direction = (value or "").strip()
    if direction not in dict(RetreatPickup.Direction.choices):
        raise ValidationError({"direction": "올바르지 않은 구분입니다."})
    return direction


from users.validators import normalize_korea_mobile_phone


def normalize_phone(raw: str) -> str | None:
    """휴대폰 번호 형식 검증·정규화. 유효하면 '010-1234-5678' 형태, 아니면 None."""
    result = normalize_korea_mobile_phone(raw or "")
    if result == "":
        return None
    return result


def _applicant_name(user) -> str:
    """등록 시점의 신청자 이름 스냅샷 (프로필 실명/표시명 → 없으면 username)."""
    try:
        profile = user.profile
    except Exception:
        profile = None
    if profile is not None:
        name = (getattr(profile, "real_name", "") or "").strip() or (
            getattr(profile, "display_name", "") or ""
        ).strip()
        if name:
            return name
    return user.get_username()


def _next_pickup_number(event: RetreatEvent, direction: str) -> int:
    current = (
        RetreatPickup.objects.filter(event=event, direction=direction).aggregate(
            m=Max("number")
        )["m"]
        or 0
    )
    return current + 1


def _allowed_boarding_places(event: RetreatEvent) -> set[str]:
    return set(
        RetreatPickupLocation.objects.filter(event=event).values_list("name", flat=True)
    )


def _validate_boarding_place(event: RetreatEvent, boarding_place: str) -> str | None:
    """등록된 위치가 있으면 목록에서만 선택 가능. 없으면 과도기적으로 자유 입력 허용."""
    allowed = _allowed_boarding_places(event)
    if not allowed:
        return None
    if boarding_place not in allowed:
        return "등록된 탑승장소 목록에서 선택해 주세요."
    return None


class RetreatEventPickupListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_view(request.user, event)
        direction = _parse_direction(request.query_params.get("direction"))
        qs = (
            event.pickups.filter(direction=direction)
            .select_related("group", "region", "division")
            .order_by("number", "id")
        )
        # 조장/부조장은 본인 조의 픽업만 조회 가능 (회장단·슈퍼유저는 전체)
        if not can_select_pickup_group(request.user, event):
            group_ids = retreat_pickup_group_ids_for(request.user, event)
            qs = qs.filter(group_id__in=group_ids)
        return Response(RetreatPickupSerializer(qs, many=True).data)

    def post(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_manage(request.user, event)

        direction = _parse_direction(request.data.get("direction"))
        name = (request.data.get("name") or "").strip()
        raw_train_time = (request.data.get("train_time") or "").strip()
        boarding_place = (request.data.get("boarding_place") or "").strip()
        contact = (request.data.get("contact") or "").strip()
        note = (request.data.get("note") or "").strip()

        errors = {}
        if not name:
            errors["name"] = "이름을 입력하세요."
        train_time = None
        if not raw_train_time:
            errors["train_time"] = "열차 시각을 입력하세요."
        else:
            train_time = parse_datetime(raw_train_time)
            if train_time is None:
                errors["train_time"] = "열차 시각 형식이 올바르지 않습니다."
            elif timezone.is_naive(train_time):
                train_time = timezone.make_aware(train_time)
        if not boarding_place:
            errors["boarding_place"] = "탑승장소를 입력하세요."
        contact_norm = ""
        if not contact:
            errors["contact"] = "연락처를 입력하세요."
        else:
            contact_norm = normalize_phone(contact)
            if contact_norm is None:
                errors["contact"] = "올바른 휴대폰 번호 형식이 아닙니다. (예: 010-1234-5678)"

        can_select = can_select_pickup_group(request.user, event)

        # 조 결정: 회장단·슈퍼유저는 요청에서 선택, 조장/부조장은 본인 조 자동 지정
        group = None
        if can_select:
            group_id = request.data.get("group")
            if group_id:
                group = RetreatGroup.objects.filter(pk=group_id, event=event).first()
                if group is None:
                    errors["group"] = "올바르지 않은 조입니다."
        else:
            group_ids = retreat_pickup_group_ids_for(request.user, event)
            if not group_ids:
                raise PermissionDenied("배정된 조가 없어 픽업을 등록할 수 없습니다.")
            group = (
                RetreatGroup.objects.filter(id__in=group_ids)
                .select_related("region", "division")
                .order_by("order", "id")
                .first()
            )

        # 지역·부서: 회장단은 직접 선택, 조장/부조장은 본인 조의 지역·부서로 자동 지정
        region = None
        division = None
        if can_select:
            region_id = request.data.get("region")
            if region_id:
                region = Region.objects.filter(pk=region_id).first()
                if region is None:
                    errors["region"] = "올바르지 않은 지역입니다."
            division_id = request.data.get("division")
            if division_id:
                division = Division.objects.filter(pk=division_id).first()
                if division is None:
                    errors["division"] = "올바르지 않은 부서입니다."
                elif region is not None and division.region_id != region.pk:
                    errors["division"] = "선택한 지역에 속하지 않는 부서입니다."
        elif group is not None:
            region = group.region
            division = group.division

        if errors:
            raise ValidationError(errors)
        contact = contact_norm

        place_err = _validate_boarding_place(event, boarding_place)
        if place_err:
            errors["boarding_place"] = place_err
            raise ValidationError(errors)

        applicant_name = _applicant_name(request.user)
        with transaction.atomic():
            pickup = RetreatPickup.objects.create(
                event=event,
                direction=direction,
                number=_next_pickup_number(event, direction),
                group=group,
                name=name,
                region=region,
                division=division,
                train_time=train_time,
                boarding_place=boarding_place,
                contact=contact,
                note=note,
                applicant_name=applicant_name,
                created_by=request.user,
            )

        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.PICKUP,
            target_id=pickup.id,
            payload_after={
                "direction": direction,
                "number": pickup.number,
                "group": group.pk if group else None,
                "name": name,
                "region": region.pk if region else None,
                "division": division.pk if division else None,
                "train_time": train_time.isoformat() if train_time else None,
                "boarding_place": boarding_place,
                "contact": contact,
                "note": note,
                "applicant_name": applicant_name,
            },
        )
        return Response(
            RetreatPickupSerializer(pickup).data,
            status=status.HTTP_201_CREATED,
        )


class RetreatPickupDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pickup_id: int):
        pickup = get_object_or_404(
            RetreatPickup.objects.select_related(
                "event", "group", "region", "division"
            ),
            pk=pickup_id,
        )
        event = pickup.event
        _assert_can_manage(request.user, event)
        can_select = can_select_pickup_group(request.user, event)
        # 조장/부조장은 본인 조의 픽업만 수정 가능
        if not can_select:
            group_ids = retreat_pickup_group_ids_for(request.user, event)
            if pickup.group_id not in group_ids:
                raise PermissionDenied("본인 조의 픽업 정보만 수정할 수 있습니다.")

        before = {
            "group": pickup.group_id,
            "name": pickup.name,
            "region": pickup.region_id,
            "division": pickup.division_id,
            "train_time": pickup.train_time.isoformat() if pickup.train_time else None,
            "boarding_place": pickup.boarding_place,
            "contact": pickup.contact,
            "note": pickup.note,
        }

        data = request.data
        errors: dict[str, str] = {}
        update_fields: list[str] = []

        if "name" in data:
            name = (data.get("name") or "").strip()
            if not name:
                errors["name"] = "이름을 입력하세요."
            else:
                pickup.name = name
                update_fields.append("name")

        if "train_time" in data:
            raw = (data.get("train_time") or "").strip()
            dt = parse_datetime(raw) if raw else None
            if dt is None:
                errors["train_time"] = "열차 시각 형식이 올바르지 않습니다."
            else:
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                pickup.train_time = dt
                update_fields.append("train_time")

        if "boarding_place" in data:
            bp = (data.get("boarding_place") or "").strip()
            if not bp:
                errors["boarding_place"] = "탑승장소를 입력하세요."
            else:
                pickup.boarding_place = bp
                update_fields.append("boarding_place")

        if "contact" in data:
            c = normalize_phone((data.get("contact") or "").strip())
            if c is None:
                errors["contact"] = (
                    "올바른 휴대폰 번호 형식이 아닙니다. (예: 010-1234-5678)"
                )
            else:
                pickup.contact = c
                update_fields.append("contact")

        if "note" in data:
            pickup.note = (data.get("note") or "").strip()
            update_fields.append("note")

        # 조·지역·부서는 회장단·슈퍼유저만 변경 가능 (조장은 본인 조 고정)
        if can_select:
            if "group" in data:
                gid = data.get("group")
                if gid:
                    grp = RetreatGroup.objects.filter(pk=gid, event=event).first()
                    if grp is None:
                        errors["group"] = "올바르지 않은 조입니다."
                    else:
                        pickup.group = grp
                else:
                    pickup.group = None
                update_fields.append("group")

            region_obj = pickup.region
            if "region" in data:
                rid = data.get("region")
                region_obj = Region.objects.filter(pk=rid).first() if rid else None
                if rid and region_obj is None:
                    errors["region"] = "올바르지 않은 지역입니다."
                pickup.region = region_obj
                update_fields.append("region")
            if "division" in data:
                did = data.get("division")
                div_obj = Division.objects.filter(pk=did).first() if did else None
                if did and div_obj is None:
                    errors["division"] = "올바르지 않은 부서입니다."
                elif (
                    div_obj is not None
                    and region_obj is not None
                    and div_obj.region_id != region_obj.pk
                ):
                    errors["division"] = "선택한 지역에 속하지 않는 부서입니다."
                pickup.division = div_obj
                update_fields.append("division")

        if errors:
            raise ValidationError(errors)
        if update_fields:
            place_err = _validate_boarding_place(event, pickup.boarding_place)
            if place_err:
                raise ValidationError({"boarding_place": place_err})
            update_fields.append("updated_at")
            pickup.save(update_fields=sorted(set(update_fields)))

        after = {
            "group": pickup.group_id,
            "name": pickup.name,
            "region": pickup.region_id,
            "division": pickup.division_id,
            "train_time": pickup.train_time.isoformat() if pickup.train_time else None,
            "boarding_place": pickup.boarding_place,
            "contact": pickup.contact,
            "note": pickup.note,
        }
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.PICKUP,
            target_id=pickup.id,
            payload_before=before,
            payload_after=after,
        )
        return Response(RetreatPickupSerializer(pickup).data)

    def delete(self, request, pickup_id: int):
        pickup = get_object_or_404(
            RetreatPickup.objects.select_related("event"),
            pk=pickup_id,
        )
        _assert_can_manage(request.user, pickup.event)
        # 조장/부조장은 본인 조의 픽업만 삭제 가능
        if not can_select_pickup_group(request.user, pickup.event):
            group_ids = retreat_pickup_group_ids_for(request.user, pickup.event)
            if pickup.group_id not in group_ids:
                raise PermissionDenied("본인 조의 픽업 정보만 삭제할 수 있습니다.")
        before = {
            "direction": pickup.direction,
            "number": pickup.number,
            "group": pickup.group_id,
            "name": pickup.name,
            "region": pickup.region_id,
            "division": pickup.division_id,
            "train_time": pickup.train_time.isoformat() if pickup.train_time else None,
            "boarding_place": pickup.boarding_place,
            "contact": pickup.contact,
            "note": pickup.note,
            "applicant_name": pickup.applicant_name,
        }
        event = pickup.event
        pid = pickup.id
        pickup.delete()
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.PICKUP,
            target_id=pid,
            payload_before=before,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
