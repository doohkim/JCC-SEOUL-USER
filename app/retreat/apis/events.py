"""행사·그룹 목록 API."""

from __future__ import annotations

from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import RetreatEvent
from retreat.serializers import RetreatEventSerializer, RetreatGroupSerializer
from users.permissions import visible_retreat_groups_for


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
            .prefetch_related("memberships__user")
            .annotate(attendee_count=Count("attendees", distinct=True))
        )
        return Response(RetreatGroupSerializer(groups, many=True).data)
