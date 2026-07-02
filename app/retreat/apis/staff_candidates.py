"""집회 운영진 배정 대기 후보 (승인된 참가 신청자 중 미배정자)."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import RetreatEvent, RetreatStaffApplication
from retreat.services.staff_application import (
    is_pastoral_staff_applicant,
    suggest_council_role,
)
from retreat.services.staff_roster import user_assigned_to_event_staff
from users.models import UserProfile
from users.permissions import can_access_retreat_tab, can_view_staff
from users.services.user_display import user_display_name


class RetreatEventStaffCandidatesView(APIView):
    """GET /api/v1/retreat/events/<event_id>/staff-candidates/

    참가 신청이 승인되었고 아직 운영 역할이 배정되지 않은 사용자.
  """

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        if not can_access_retreat_tab(request.user):
            raise PermissionDenied("수련회 화면 접근 권한이 없습니다.")

        event = get_object_or_404(RetreatEvent, pk=event_id)
        if not (request.user.is_superuser or can_view_staff(request.user, event)):
            raise PermissionDenied("집회 운영진 명단 조회 권한이 없습니다.")

        applications = (
            RetreatStaffApplication.objects.filter(
                event=event,
                status=RetreatStaffApplication.Status.APPROVED,
                user__is_active=True,
                user__retired_at__isnull=True,
                user__profile__onboarding_status=UserProfile.OnboardingStatus.APPROVED,
            )
            .select_related(
                "user",
                "user__profile",
                "region",
                "division",
                "group",
                "group__region",
                "group__division",
            )
            .order_by("-reviewed_at", "-created_at", "-id")
        )

        results = []
        seen_user_ids: set[int] = set()
        for app in applications:
            if app.user_id in seen_user_ids:
                continue
            if user_assigned_to_event_staff(app.user, event):
                continue
            seen_user_ids.add(app.user_id)

            profile = getattr(app.user, "profile", None)
            phone = (getattr(profile, "phone", "") or "").strip()
            name = (
                (getattr(profile, "real_name", "") or "").strip()
                or user_display_name(app.user)
                or app.user.username
            )
            pastoral = is_pastoral_staff_applicant(app.user)
            group = app.group
            results.append(
                {
                    "id": app.id,
                    "application_id": app.id,
                    "user_id": app.user_id,
                    "name": name,
                    "phone": phone,
                    "region_name": app.region.name if app.region_id else "",
                    "division_name": app.division.name if app.division_id else "",
                    "region_id": app.region_id,
                    "division_id": app.division_id,
                    "group_id": group.id if group else None,
                    "group_name": group.name if group else "",
                    "group_role": app.group_role or "",
                    "is_pastoral": pastoral,
                    "suggested_council_role": (
                        (app.approved_council_role or suggest_council_role(app))
                        if pastoral
                        else ""
                    ),
                }
            )
        return Response(results)
