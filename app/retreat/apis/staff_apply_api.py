"""운영진 참가 신청서 API (React)."""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.forms import RetreatStaffApplicationForm
from retreat.models import RetreatEvent, RetreatGroupMembership, RetreatStaffApplication, StaffApplicationTrack
from retreat.services.staff_application import (
    eligible_groups_for_member,
    eligible_groups_payload_for_member,
    event_staff_status,
    has_retreat_operational_access,
    is_pastoral_staff_applicant,
    member_can_apply_to_event,
    primary_affiliation_for,
    staff_applicant_tier,
    staff_applicant_tier_label,
)
from users.permissions import can_access_retreat_staff_apply


def _build_staff_apply_payload(user, event: RetreatEvent) -> dict:
    status_value = event_staff_status(user, event)
    tier = staff_applicant_tier(user)
    region, division = primary_affiliation_for(user)
    eligible_groups = eligible_groups_for_member(user, event)
    can_apply, apply_block_message = member_can_apply_to_event(
        user, event, eligible_groups=eligible_groups
    )
    is_pastoral = tier in ("pastor", "evangelist")
    read_only = status_value in ("pending", "approved")

    application = (
        RetreatStaffApplication.objects.filter(
            event=event,
            user=user,
            status__in=[
                RetreatStaffApplication.Status.PENDING,
                RetreatStaffApplication.Status.APPROVED,
            ],
        )
        .select_related("region", "division", "group")
        .order_by("-created_at", "-id")
        .first()
    )

    rejected = (
        RetreatStaffApplication.objects.filter(
            event=event,
            user=user,
            status=RetreatStaffApplication.Status.REJECTED,
        )
        .order_by("-reviewed_at", "-id")
        .first()
    )

    application_payload = None
    if application:
        application_payload = {
            "application_track": application.application_track,
            "group_id": application.group_id,
            "group_role": application.group_role,
            "status": application.status,
        }

    return {
        "event": {
            "id": event.id,
            "name": event.name,
            "staff_applications_open": event.staff_applications_open,
        },
        "staff_status": status_value,
        "read_only": read_only,
        "is_pastoral": is_pastoral,
        "applicant_tier": tier,
        "applicant_tier_label": staff_applicant_tier_label(tier),
        "fixed_region_name": region.name if region else "",
        "fixed_division_name": division.name if division else "",
        "region_id": region.id if region else None,
        "division_id": division.id if division else None,
        "eligible_groups": eligible_groups_payload_for_member(user, event),
        "can_submit_application": can_apply and status_value == "open" and not read_only,
        "apply_block_message": apply_block_message,
        "show_ineligible_card": (
            status_value in ("open", "rejected")
            and not read_only
            and tier == "member"
            and not can_apply
        ),
        "rejection_reason": rejected.rejection_reason if rejected else "",
        "has_operational_access": has_retreat_operational_access(user, event),
        "application_track_choices": [
            {"value": value, "label": label}
            for value, label in StaffApplicationTrack.choices
        ],
        "group_role_choices": [
            {"value": value, "label": label}
            for value, label in RetreatGroupMembership.Role.choices
        ],
        "application": application_payload,
        "default_application_track": StaffApplicationTrack.GROUP_LEADERSHIP,
    }


class RetreatEventStaffApplyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        if not can_access_retreat_staff_apply(request.user):
            raise PermissionDenied("참가 신청을 이용할 권한이 없습니다.")
        event = get_object_or_404(RetreatEvent, pk=event_id, is_active=True)
        return Response(_build_staff_apply_payload(request.user, event))

    def post(self, request, event_id: int):
        if not can_access_retreat_staff_apply(request.user):
            raise PermissionDenied("참가 신청을 이용할 권한이 없습니다.")
        event = get_object_or_404(RetreatEvent, pk=event_id, is_active=True)
        if event_staff_status(request.user, event) != "open":
            raise PermissionDenied("신청을 제출할 수 없습니다.")

        user = request.user
        region, division = primary_affiliation_for(user)
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        if region:
            data.setdefault("region", region.id)
        if division:
            data.setdefault("division", division.id)

        form = RetreatStaffApplicationForm(
            data=data,
            event=event,
            user=user,
            read_only=False,
        )
        if not form.is_valid():
            raise ValidationError(form.errors)

        try:
            application = form.save()
        except DjangoValidationError as exc:
            raise ValidationError({"detail": exc.messages}) from exc

        payload = _build_staff_apply_payload(user, event)
        payload["application"] = {
            "application_track": application.application_track,
            "group_id": application.group_id,
            "group_role": application.group_role,
            "status": application.status,
        }
        return Response(
            {
                "message": "신청이 접수되었습니다. 승인 후 운영 화면이 열립니다.",
                **payload,
            },
            status=status.HTTP_201_CREATED,
        )
