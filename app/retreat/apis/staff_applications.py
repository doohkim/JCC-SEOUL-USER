"""운영진 참가 신청 API."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import RetreatEvent, RetreatStaffApplication
from retreat.serializers.staff_application import (
    RetreatStaffApplicationReviewSerializer,
    RetreatStaffApplicationSerializer,
)
from retreat.services.account_retired import visible_user_linked_for
from retreat.services.staff_application import (
    apply_staff_application,
    reject_staff_application,
)
from users.permissions import can_access_retreat_tab, can_manage_staff


def _assert_manage(user, event: RetreatEvent) -> None:
    if not can_access_retreat_tab(user):
        raise PermissionDenied
    if not can_manage_staff(user, event):
        raise PermissionDenied("참가 신청 승인·반려 권한이 없습니다.")


class RetreatEventStaffApplicationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_manage(request.user, event)
        status_filter = (request.query_params.get("status") or "pending").strip()
        qs = (
            RetreatStaffApplication.objects.filter(event=event)
            .select_related(
                "user",
                "user__profile",
                "region",
                "division",
                "group",
            )
            .order_by("-created_at", "-id")
        )
        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)
        qs = visible_user_linked_for(request.user, qs, user_prefix="user")
        data = RetreatStaffApplicationSerializer(qs, many=True).data
        return Response({"results": data})


class RetreatStaffApplicationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id: int, application_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_manage(request.user, event)
        application = get_object_or_404(
            RetreatStaffApplication,
            pk=application_id,
            event=event,
        )
        serializer = RetreatStaffApplicationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        try:
            if action == "approve":
                council_role = (
                    serializer.validated_data.get("council_role") or ""
                ).strip() or None
                group_id = serializer.validated_data.get("group_id")
                group_role = (
                    serializer.validated_data.get("group_role") or ""
                ).strip() or None
                application = apply_staff_application(
                    application,
                    reviewer=request.user,
                    council_role=council_role,
                    group_id=group_id,
                    group_role=group_role,
                )
            else:
                application = reject_staff_application(
                    application,
                    reviewer=request.user,
                    reason=serializer.validated_data.get("rejection_reason") or "",
                )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(
            RetreatStaffApplicationSerializer(application).data,
            status=status.HTTP_200_OK,
        )
