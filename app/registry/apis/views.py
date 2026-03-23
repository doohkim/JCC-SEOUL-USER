from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from registry.models import MemberDivisionTeam
from registry.serializers import (
    MemberDivisionTeamSerializer,
    OrgChangeTeamSerializer,
    OrgTransferDivisionSerializer,
)
from users.permissions import IsPastoralRegistryStaff


class OrgChangeTeamView(APIView):
    """
    같은 부서 내 팀 변경.

    POST JSON 예::

        {
          "member_id": 1,
          "division_id": 2,
          "new_team_id": 10,
          "membership_id": 5,
          "make_primary": true
        }
    """

    permission_classes = [IsPastoralRegistryStaff]

    def post(self, request, *args, **kwargs):
        ser = OrgChangeTeamSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            mdt = ser.save()
        except DjangoValidationError as e:
            body = {"detail": list(e.messages)}
            if getattr(e, "error_dict", None):
                body["fields"] = {
                    k: [str(x) for x in v] for k, v in e.error_dict.items()
                }
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            MemberDivisionTeamSerializer(mdt).data,
            status=status.HTTP_200_OK,
        )


class OrgTransferDivisionView(APIView):
    """
    부서 이전.

    POST JSON 예::

        {
          "member_id": 1,
          "from_division_id": 2,
          "to_division_id": 3,
          "team_id": 12,
          "remove_from_source": true,
          "make_primary": true
        }
    """

    permission_classes = [IsPastoralRegistryStaff]

    def post(self, request, *args, **kwargs):
        ser = OrgTransferDivisionSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            mdt = ser.save()
        except DjangoValidationError as e:
            body = {"detail": list(e.messages)}
            if getattr(e, "error_dict", None):
                body["fields"] = {
                    k: [str(x) for x in v] for k, v in e.error_dict.items()
                }
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            MemberDivisionTeamSerializer(mdt).data,
            status=status.HTTP_200_OK,
        )


class MemberMembershipListView(APIView):
    """멤버의 부서·팀 소속 목록 (조회). GET ``?member_id=``"""

    permission_classes = [IsPastoralRegistryStaff]

    def get(self, request, *args, **kwargs):
        mid = request.query_params.get("member_id")
        if not mid:
            return Response(
                {"detail": "member_id 쿼리가 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = MemberDivisionTeam.objects.filter(member_id=mid).select_related(
            "division", "team"
        )
        return Response(MemberDivisionTeamSerializer(qs, many=True).data)
