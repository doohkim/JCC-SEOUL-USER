"""함께하기(공지) 목록·상세 API."""

from __future__ import annotations

from django.db.models import F, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notices.models import Notice
from notices.serializers import NoticeDetailSerializer, NoticeListSerializer
from users.permissions import can_access_notices_tab


class NoticeListAPIView(APIView):
    """GET ``/api/v1/notices/`` — 함께하기 공지 카드 목록."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_access_notices_tab(request.user):
            return Response(
                {"detail": "notice access not allowed"},
                status=status.HTTP_403_FORBIDDEN,
            )

        q = (request.query_params.get("q") or "").strip()
        category_slug = (request.query_params.get("category") or "").strip()
        try:
            page = max(1, int(request.query_params.get("page", "1")))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(
                50, max(1, int(request.query_params.get("page_size", "12")))
            )
        except (TypeError, ValueError):
            page_size = 12

        qs = Notice.visible_queryset()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
        if category_slug:
            qs = qs.filter(category__slug=category_slug, category__is_active=True)

        total = qs.count()
        offset = (page - 1) * page_size
        items = qs[offset : offset + page_size]
        serializer = NoticeListSerializer(
            items, many=True, context={"request": request}
        )
        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": serializer.data,
            }
        )


class NoticeDetailAPIView(APIView):
    """GET ``/api/v1/notices/<id>/`` — 공지 상세 (조회수 +1)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, notice_id: int):
        if not can_access_notices_tab(request.user):
            return Response(
                {"detail": "notice access not allowed"},
                status=status.HTTP_403_FORBIDDEN,
            )

        notice = (
            Notice.objects.select_related(
                "created_by", "division", "division__region", "category"
            )
            .filter(pk=notice_id)
            .first()
        )
        if notice is None:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)

        Notice.objects.filter(pk=notice.pk).update(view_count=F("view_count") + 1)
        notice.view_count += 1
        serializer = NoticeDetailSerializer(notice, context={"request": request})
        return Response(serializer.data)
