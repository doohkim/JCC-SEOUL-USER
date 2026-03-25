"""상담 REST API."""

from __future__ import annotations

import datetime as dt

from django.http import Http404
from django.urls import reverse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from counseling.models import CounselorDayOverride, CounselingRequest, CounselingSlot
from counseling.serializers import (
    CounselorDayOverrideSerializer,
    CounselorScheduleSettingsSerializer,
    CounselingRequestCreateSerializer,
    CounselingRequestSerializer,
    CounselingRequestUpdateSerializer,
    CounselingSlotSerializer,
)
from counseling.services import (
    accept_counseling_request,
    cancel_counseling_request,
    create_counseling_request,
    ensure_slots_for_horizon,
    get_or_create_schedule_settings,
    reject_counseling_request,
)
from counseling.services.notifications import notify_new_counseling_request
from counseling.services.slots import counseling_request_detail_for_user, date_range_horizon
from users.permissions import (
    IsCounselingCounselor,
    IsCounselingParticipant,
    can_access_counseling_manage_tab,
    counselors_queryset_for_applicant,
)


def _parse_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


class CounselorListApiView(APIView):
    """목사·전도사 목록(부서 격리)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = counselors_queryset_for_applicant(request.user).select_related("role_level")
        from users.services.user_display import user_display_name

        data = [{"id": u.pk, "label": user_display_name(u)} for u in qs.order_by("id")]
        return Response(data)


class CounselorSlotsApiView(APIView):
    """특정 상담사의 예약 가능 슬롯(OPEN만)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        if not counselors_queryset_for_applicant(request.user).filter(pk=pk).exists():
            raise Http404()
        ensure_slots_for_horizon(pk)
        start_d, end_d = date_range_horizon()
        from_q = _parse_date(request.query_params.get("from")) or start_d
        to_q = _parse_date(request.query_params.get("to")) or end_d
        if from_q > to_q:
            from_q, to_q = to_q, from_q
        qs = CounselingSlot.objects.filter(
            counselor_id=pk,
            date__gte=from_q,
            date__lte=to_q,
            state=CounselingSlot.State.OPEN,
        ).order_by("date", "start_time")
        return Response(CounselingSlotSerializer(qs, many=True).data)


class CounselorManageSlotsApiView(APIView):
    """상담사 본인 슬롯 전체 상태(관리 화면)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_access_counseling_manage_tab(request.user):
            return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        ensure_slots_for_horizon(request.user.pk)
        start_d, end_d = date_range_horizon()
        from_q = _parse_date(request.query_params.get("from")) or start_d
        to_q = _parse_date(request.query_params.get("to")) or end_d
        qs = CounselingSlot.objects.filter(
            counselor_id=request.user.pk,
            date__gte=from_q,
            date__lte=to_q,
        ).order_by("date", "start_time")
        return Response(CounselingSlotSerializer(qs, many=True).data)


class CounselorSettingsApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_access_counseling_manage_tab(request.user):
            return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        obj = get_or_create_schedule_settings(request.user.pk)
        return Response(CounselorScheduleSettingsSerializer(obj).data)

    def patch(self, request):
        if not can_access_counseling_manage_tab(request.user):
            return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        obj = get_or_create_schedule_settings(request.user.pk)
        ser = CounselorScheduleSettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        ensure_slots_for_horizon(request.user.pk)
        return Response(ser.data)


class CounselorDayOverrideListApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_access_counseling_manage_tab(request.user):
            return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        start_d, end_d = date_range_horizon()
        qs = CounselorDayOverride.objects.filter(
            counselor_id=request.user.pk,
            date__gte=start_d,
            date__lte=end_d,
        ).order_by("date")
        return Response(CounselorDayOverrideSerializer(qs, many=True).data)

    def post(self, request):
        if not can_access_counseling_manage_tab(request.user):
            return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        ser = CounselorDayOverrideSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = CounselorDayOverride.objects.update_or_create(
            counselor_id=request.user.pk,
            date=ser.validated_data["date"],
            defaults={
                "is_closed": ser.validated_data.get("is_closed", False),
                "custom_slots_json": ser.validated_data.get("custom_slots_json"),
            },
        )[0]
        ensure_slots_for_horizon(request.user.pk)
        return Response(
            CounselorDayOverrideSerializer(obj).data,
            status=status.HTTP_201_CREATED,
        )


class CounselorDayOverrideDetailApiView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, date_str: str):
        if not can_access_counseling_manage_tab(request.user):
            return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        try:
            day = dt.date.fromisoformat(date_str)
        except ValueError:
            return Response({"detail": "날짜 형식은 YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        obj = CounselorDayOverride.objects.filter(
            counselor_id=request.user.pk,
            date=day,
        ).first()
        if not obj:
            return Response({"detail": "없음"}, status=status.HTTP_404_NOT_FOUND)
        ser = CounselorDayOverrideSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        ensure_slots_for_horizon(request.user.pk)
        return Response(ser.data)

    def delete(self, request, date_str: str):
        if not can_access_counseling_manage_tab(request.user):
            return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        try:
            day = dt.date.fromisoformat(date_str)
        except ValueError:
            return Response({"detail": "날짜 형식은 YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = CounselorDayOverride.objects.filter(
            counselor_id=request.user.pk,
            date=day,
        ).delete()
        if not deleted:
            return Response({"detail": "없음"}, status=status.HTTP_404_NOT_FOUND)
        ensure_slots_for_horizon(request.user.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CounselingRequestListCreateApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        box = request.query_params.get("box", "outgoing")
        if box == "incoming":
            if not can_access_counseling_manage_tab(request.user):
                return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
            qs = CounselingRequest.objects.filter(counselor_id=request.user.pk).select_related(
                "slot", "applicant", "counselor"
            )
        else:
            qs = CounselingRequest.objects.filter(applicant_id=request.user.pk).select_related(
                "slot", "applicant", "counselor"
            )
        qs = qs.order_by("-created_at")
        ser = CounselingRequestSerializer(qs, many=True, context={"request": request})
        return Response(ser.data)

    def post(self, request):
        ser = CounselingRequestCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        slot_id = ser.validated_data["slot_id"]
        slot = CounselingSlot.objects.filter(pk=slot_id).first()
        if not slot:
            return Response({"detail": "슬롯을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        if not counselors_queryset_for_applicant(request.user).filter(pk=slot.counselor_id).exists():
            return Response({"detail": "해당 상담사에게 신청할 수 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        try:
            req = create_counseling_request(
                applicant_id=request.user.pk,
                slot_id=slot_id,
                message=ser.validated_data.get("applicant_message") or "",
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        req = CounselingRequest.objects.select_related("slot", "applicant", "counselor").get(pk=req.pk)
        detail_path = reverse("counseling_request_detail", kwargs={"public_id": str(req.public_id)})
        notify_new_counseling_request(
            req,
            absolute_detail_url=request.build_absolute_uri(detail_path),
        )
        return Response(
            CounselingRequestSerializer(req, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class CounselingRequestDetailApiView(APIView):
    permission_classes = [IsAuthenticated, IsCounselingParticipant]

    def get_object(self):
        public_id = self.kwargs["public_id"]
        req = counseling_request_detail_for_user(user=self.request.user, public_id=public_id)
        self.check_object_permissions(self.request, req)
        return req

    def get(self, request, public_id):
        req = self.get_object()
        return Response(CounselingRequestSerializer(req, context={"request": request}).data)

    def patch(self, request, public_id):
        req = self.get_object()
        ser = CounselingRequestUpdateSerializer(
            req,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        req.refresh_from_db()
        return Response(CounselingRequestSerializer(req, context={"request": request}).data)

    def delete(self, request, public_id):
        req = self.get_object()
        if req.applicant_id != request.user.pk:
            return Response({"detail": "신청자만 취소할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)
        try:
            cancel_counseling_request(user_id=request.user.pk, req=req)
        except (PermissionError, ValueError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CounselingRequestAcceptApiView(APIView):
    permission_classes = [IsAuthenticated, IsCounselingParticipant, IsCounselingCounselor]

    def post(self, request, public_id):
        req = counseling_request_detail_for_user(user=request.user, public_id=public_id)
        self.check_object_permissions(self.request, req)
        try:
            accept_counseling_request(user_id=request.user.pk, req=req)
        except (PermissionError, ValueError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        req.refresh_from_db()
        return Response(CounselingRequestSerializer(req, context={"request": request}).data)


class CounselingRequestRejectApiView(APIView):
    permission_classes = [IsAuthenticated, IsCounselingParticipant, IsCounselingCounselor]

    def post(self, request, public_id):
        req = counseling_request_detail_for_user(user=request.user, public_id=public_id)
        self.check_object_permissions(self.request, req)
        try:
            reject_counseling_request(user_id=request.user.pk, req=req)
        except (PermissionError, ValueError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        req.refresh_from_db()
        return Response(CounselingRequestSerializer(req, context={"request": request}).data)
