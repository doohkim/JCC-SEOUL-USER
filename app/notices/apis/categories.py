"""공지 카테고리 목록 API."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notices.models import Notice
from notices.serializers import NoticeCategorySerializer


class NoticeCategoryListAPIView(APIView):
    """활성 공지 카테고리 목록 — 작성·필터 UI용."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        categories = Notice.active_categories()
        serializer = NoticeCategorySerializer(categories, many=True)
        return Response(serializer.data)
