from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from collections import defaultdict

from registry.models import (
    Member,
    MemberDivisionTeam,
    MemberFamilyMember,
    MemberProfile,
    MemberVisitLog,
)
from registry.serializers.member_crud import (
    MemberFamilyMemberSerializer,
    MemberProfileSerializer,
    MemberSerializer,
    MemberVisitLogSerializer,
)
from attendance.choices.attendance import MidweekServiceType
from attendance.models.weekly import MidweekAttendanceRecord, SundayAttendanceLine
from users.models import Division, Role, Team
from users.permissions import IsPastoralRegistryStaff, members_visible_to, registry_divisions_for


class MemberListCreateView(APIView):
    """교적(Member) 목록 / 생성."""

    permission_classes = [IsPastoralRegistryStaff]

    def get(self, request, *args, **kwargs):
        q = (request.query_params.get("q") or "").strip()
        division_code = (request.query_params.get("division_code") or "").strip() or None
        team_id_raw = (request.query_params.get("team_id") or "").strip() or None
        team_id = None
        if team_id_raw:
            try:
                team_id = int(team_id_raw)
            except ValueError:
                team_id = None
        limit = int(request.query_params.get("limit") or 50)
        offset = int(request.query_params.get("offset") or 0)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        division = None
        if division_code:
            try:
                division = Division.objects.get(code=division_code)
            except Division.DoesNotExist:
                division = None

        qs = members_visible_to(request.user, division=division).select_related("pastoral_profile")
        if team_id is not None:
            qs = qs.filter(division_teams__team_id=team_id)
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(name_alias__icontains=q)
                | Q(pastoral_profile__phone__icontains=q)
            )

        total = qs.count()
        page = qs.order_by("name")[offset : offset + limit]

        out = []
        for m in page:
            mdt = (
                m.division_teams.select_related("team", "division")
                .order_by("-is_primary", "sort_order", "id")
                .first()
            )
            try:
                phone = m.pastoral_profile.phone
            except MemberProfile.DoesNotExist:
                phone = ""
            out.append(
                {
                    "id": m.id,
                    "name": m.name,
                    "name_alias": m.name_alias,
                    "is_active": m.is_active,
                    "phone": phone,
                    "division_id": mdt.division_id if mdt else None,
                    "division_code": mdt.division.code if mdt and mdt.division_id else "",
                    "team_id": mdt.team_id if mdt else None,
                    "team_name": mdt.team.name if mdt and mdt.team_id else "",
                    "membership_id": mdt.id if mdt else None,
                    "division_name": mdt.division.name if mdt and mdt.division_id else "",
                    "is_primary": bool(mdt.is_primary) if mdt else False,
                }
            )

        return Response({"count": total, "results": out})

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        # member
        member_ser = MemberSerializer(data=request.data)
        if not member_ser.is_valid():
            return Response(member_ser.errors, status=status.HTTP_400_BAD_REQUEST)
        m = member_ser.save()

        profile = Member.objects.get(pk=m.pk).pastoral_profile  # ensured by signal
        profile_ser = MemberProfileSerializer(instance=profile, data=request.data, partial=True)
        if not profile_ser.is_valid():
            return Response(profile_ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            profile_ser.save()
        except DjangoValidationError as e:
            return Response({"detail": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"ok": True, "member_id": m.id}, status=status.HTTP_201_CREATED)


def _normalize_hoejangdan_label(name: str) -> str:
    """표시용 팀명 정규화 (부서 회장단/팀 회장단 -> 회장단)."""
    label = (name or "").strip()
    compact = "".join(label.split())
    # 팀명에 공백/접두·접미 정보가 붙어 있어도(예: "부서 회장단", "회장단(XX)")
    # 화면에는 일관되게 "회장단"으로 표시한다.
    if "회장단" in compact:
        return "회장단"
    return label


class MemberRegistryTeamsAccordionView(APIView):
    """
    교적부 목록용 팀/부서/팀원 구조 응답.

    GET query:
    - division_code (선택)
    - team_id (선택)
    - q (선택): 멤버 이름/별칭/연락처 검색
    - meta_only=1 (선택): 팀 옵션만 반환 (멤버 배열 비움)
    """

    permission_classes = [IsPastoralRegistryStaff]

    def get(self, request, *args, **kwargs):
        q = (request.query_params.get("q") or "").strip()
        division_code = (request.query_params.get("division_code") or "").strip() or None
        team_id_raw = (request.query_params.get("team_id") or "").strip() or None
        meta_only = (request.query_params.get("meta_only") or "").strip() in {"1", "true", "True"}

        team_id = None
        if team_id_raw:
            try:
                team_id = int(team_id_raw)
            except ValueError:
                team_id = None

        divisions_qs = registry_divisions_for(request.user).order_by("sort_order", "name")
        if division_code:
            div = divisions_qs.filter(code=division_code).first()
            if not div:
                return Response({"detail": "division_code not allowed"}, status=status.HTTP_403_FORBIDDEN)
            divisions_qs = divisions_qs.filter(pk=div.pk)

        # meta_only=1: 멤버 그룹/검색 로직은 필요 없고,
        # 폼에서 부서/팀 선택을 위해 "현재 사용자가 접근 가능한 모든 팀"을 반환합니다.
        if meta_only:
            division_options = [
                {"code": d.code, "id": d.id, "name": d.name}
                for d in divisions_qs
            ]

            team_options_qs = (
                Team.objects.filter(division__in=divisions_qs)
                .select_related("division")
                .order_by("sort_order", "name")
            )
            team_options = [
                {
                    "id": t.id,
                    "division_code": t.division.code if t.division_id else "",
                    "name": _normalize_hoejangdan_label(t.name) if t.id else "",
                }
                for t in team_options_qs
            ]

            return Response(
                {
                    "division_options": division_options,
                    "team_options": team_options,
                    "groups": [],
                }
            )

        members_qs = (
            MemberDivisionTeam.objects.filter(
                member__is_active=True,
                division__in=divisions_qs,
            )
            .select_related(
                "member",
                "member__pastoral_profile",
                "team",
                "division",
            )
        )

        if q:
            members_qs = members_qs.filter(
                Q(member__name__icontains=q)
                | Q(member__name_alias__icontains=q)
                | Q(member__pastoral_profile__phone__icontains=q)
            )

        members_qs = members_qs.order_by(
            # 멤버당 "1개 소속 행만" 선택하기 위한 정렬:
            # - is_primary 우선
            # - 그 다음 sort_order
            # - 마지막으로 id로 안정화
            "member_id",
            "-is_primary",
            "sort_order",
            "id",
        )

        # For meta options
        division_options = []
        team_options = []
        seen_team_ids = set()
        seen_division_ids = set()

        # group by team
        groups: dict[int | None, dict] = {}

        hoejangdan_label = "회장단"

        def _is_hoejangdan_team(r: MemberDivisionTeam) -> bool:
            if not r.team_id:
                return False
            try:
                return _normalize_hoejangdan_label(r.team.name) == hoejangdan_label
            except Exception:
                return False

        # 1) 멤버당 대표 1행을 고른다.
        # 2) 기본은 정렬 순서(=우선 소속)이지만,
        #    멤버가 회장단 팀에 포함되어 있으면 대표를 회장단으로 보정한다.
        best_row_by_member: dict[int, MemberDivisionTeam] = {}
        for row in members_qs:
            # 팀 필터는 "대표 1행 선택" 전에 적용한다.
            if team_id is not None and row.team_id != team_id:
                continue

            mid = row.member_id
            cur = best_row_by_member.get(mid)
            if cur is None:
                best_row_by_member[mid] = row
                continue

            # 회장단이 아닌 대표가 이미 있어도,
            # 현재 row가 회장단이면 대표를 교체한다.
            if _is_hoejangdan_team(row) and not _is_hoejangdan_team(cur):
                best_row_by_member[mid] = row

        chosen_rows = sorted(
            best_row_by_member.values(),
            key=lambda r: (
                r.member_id,
                -(1 if r.is_primary else 0),
                r.sort_order,
                r.id,
            ),
        )

        for row in chosen_rows:
            div = row.division
            if div and div.id not in seen_division_ids:
                seen_division_ids.add(div.id)
                division_options.append({"code": div.code, "id": div.id, "name": div.name})

            t_id = row.team_id
            if t_id is not None and t_id not in seen_team_ids:
                seen_team_ids.add(t_id)
                team_label = _normalize_hoejangdan_label(row.team.name) if row.team_id else "팀 미지정"
                team_options.append(
                    {
                        "id": t_id,
                        "division_code": div.code if div else "",
                        "label": team_label,
                        "name": team_label,
                    }
                )

            if t_id not in groups:
                groups[t_id] = {
                    "division_id": div.id if div else None,
                    "division_code": div.code if div else "",
                    "division_name": div.name if div else "",
                    "team_id": t_id,
                    "team_name": _normalize_hoejangdan_label(row.team.name) if row.team_id else "팀 미지정",
                    "members": [],
                }

            phone = ""
            try:
                phone = row.member.pastoral_profile.phone
            except Exception:
                phone = ""

            groups[t_id]["members"].append(
                {
                    "id": row.member_id,
                    "name": row.member.name,
                    "name_alias": row.member.name_alias,
                    "phone": phone,
                    "is_active": True,
                    "membership_id": row.id,
                    "team_id": row.team_id,
                    "division_id": row.division_id,
                    "division_code": row.division.code if row.division_id else "",
                }
            )

        # 그룹 내부 회원 정렬(프론트에서도 정렬하지만,
        # 여기서 먼저 하면 group_list 정렬 키가 안정화됩니다.)
        for g in groups.values():
            g["members"].sort(key=lambda m: (m.get("name") or ""))

        # sort teams by name
        group_list = list(groups.values())
        group_list.sort(key=lambda g: (g["team_name"] or "", g["members"][0]["name"] if g["members"] else ""))

        if meta_only:
            # hide members in meta mode
            group_list = []

        return Response(
            {
                "division_options": [{"code": d["code"], "name": d["name"]} for d in division_options],
                "team_options": [
                    {"id": t["id"], "division_code": t["division_code"], "name": t["name"]}
                    for t in team_options
                ],
                "groups": group_list,
            }
        )


class MemberDetailUpdateView(APIView):
    """교적 상세 / 수정."""

    permission_classes = [IsPastoralRegistryStaff]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_visible_member(self, request, member_id: int) -> Member:
        qs = members_visible_to(request.user)
        try:
            return qs.get(pk=member_id)
        except Member.DoesNotExist as e:
            raise Http404("member not found") from e

    def _build_detail(self, member: Member) -> dict:
        try:
            profile = member.pastoral_profile
        except MemberProfile.DoesNotExist:
            profile = None

        primary_mdt = (
            member.division_teams.select_related("team", "division")
            .order_by("-is_primary", "sort_order", "id")
            .first()
        )

        family = (
            MemberFamilyMember.objects.filter(member=member)
            .select_related("division")
            .order_by("sort_order", "id")
        )
        # 상세 화면에서는 "최신 1개만" 표시합니다.
        visits = (
            MemberVisitLog.objects.filter(member=member)
            .select_related("recorded_by")
            .order_by("-visit_date", "-created_at")[:1]
        )

        # 최근 출석(수요/토요/주일) 날짜 1개만 표시
        last_sunday = (
            SundayAttendanceLine.objects.filter(member=member)
            .order_by("-service_date")
            .first()
        )
        last_midweek = (
            MidweekAttendanceRecord.objects.filter(member=member, status__isnull=False)
            .order_by("-service_date")
            .first()
        )

        recent_attendance = {"date": "", "label": ""}
        if last_sunday and last_midweek:
            if last_midweek.service_date >= last_sunday.service_date:
                if last_midweek.service_type == MidweekServiceType.SATURDAY:
                    recent_attendance = {
                        "date": last_midweek.service_date.isoformat(),
                        "label": "토요예배",
                    }
                else:
                    recent_attendance = {
                        "date": last_midweek.service_date.isoformat(),
                        "label": "수요예배",
                    }
            else:
                recent_attendance = {
                    "date": last_sunday.service_date.isoformat(),
                    "label": "일요일예배",
                }
        elif last_midweek:
            if last_midweek.service_type == MidweekServiceType.SATURDAY:
                recent_attendance = {
                    "date": last_midweek.service_date.isoformat(),
                    "label": "토요예배",
                }
            else:
                recent_attendance = {
                    "date": last_midweek.service_date.isoformat(),
                    "label": "수요예배",
                }
        elif last_sunday:
            recent_attendance = {
                "date": last_sunday.service_date.isoformat(),
                "label": "일요일예배",
            }

        return {
            "member": {
                "id": member.id,
                "name": member.name,
                "name_alias": member.name_alias,
                "is_active": member.is_active,
            },
            "profile": MemberProfileSerializer(profile).data if profile else None,
            "primary_membership": {
                "division_id": primary_mdt.division_id if primary_mdt and primary_mdt.division_id else None,
                "division_code": primary_mdt.division.code if primary_mdt and primary_mdt.division_id else "",
                "division_name": primary_mdt.division.name if primary_mdt and primary_mdt.division_id else "",
                "team_id": primary_mdt.team_id if primary_mdt and primary_mdt.team_id else None,
                "team_name": primary_mdt.team.name if primary_mdt and primary_mdt.team_id else "팀 미지정",
                "membership_id": primary_mdt.id if primary_mdt else None,
                "is_primary": bool(primary_mdt.is_primary) if primary_mdt else False,
            },
            "recent_attendance": recent_attendance,
            "family": MemberFamilyMemberSerializer(family, many=True).data,
            "visits": MemberVisitLogSerializer(visits, many=True).data,
        }

    def get(self, request, member_id: int, *args, **kwargs):
        m = self._get_visible_member(request, member_id)
        return Response(self._build_detail(m))

    @transaction.atomic
    def put(self, request, member_id: int, *args, **kwargs):
        return self._patch(request, member_id, partial=False)

    @transaction.atomic
    def patch(self, request, member_id: int, *args, **kwargs):
        return self._patch(request, member_id, partial=True)

    def _patch(self, request, member_id: int, *, partial: bool):
        m = self._get_visible_member(request, member_id)

        member_ser = MemberSerializer(instance=m, data=request.data, partial=partial)
        if not member_ser.is_valid():
            return Response(member_ser.errors, status=status.HTTP_400_BAD_REQUEST)
        member_ser.save()

        profile = m.pastoral_profile
        profile_ser = MemberProfileSerializer(instance=profile, data=request.data, partial=True)
        if not profile_ser.is_valid():
            return Response(profile_ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            profile_ser.save()
        except DjangoValidationError as e:
            return Response({"detail": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"ok": True})


class MemberFamilyListCreateView(APIView):
    permission_classes = [IsPastoralRegistryStaff]

    def _get_visible_member(self, request, member_id: int) -> Member:
        qs = members_visible_to(request.user)
        try:
            return qs.get(pk=member_id)
        except Member.DoesNotExist as e:
            raise Http404("member not found") from e

    def get(self, request, member_id: int, *args, **kwargs):
        m = self._get_visible_member(request, member_id)
        family = (
            MemberFamilyMember.objects.filter(member=m)
            .select_related("division")
            .order_by("sort_order", "id")
        )
        return Response(MemberFamilyMemberSerializer(family, many=True).data)

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @transaction.atomic
    def post(self, request, member_id: int, *args, **kwargs):
        m = self._get_visible_member(request, member_id)
        ser = MemberFamilyMemberSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            obj = ser.save(member=m)
        except DjangoValidationError as e:
            return Response({"detail": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MemberFamilyMemberSerializer(obj).data, status=status.HTTP_201_CREATED)


class MemberFamilyDetailView(APIView):
    permission_classes = [IsPastoralRegistryStaff]

    def _get_family_in_visible_member(self, request, family_id: int) -> MemberFamilyMember:
        qs = members_visible_to(request.user)
        obj = MemberFamilyMember.objects.select_related("member").filter(
            id=family_id, member__in=qs
        ).first()
        if not obj:
            raise Http404("family not found")
        return obj

    def get(self, request, family_id: int, *args, **kwargs):
        obj = self._get_family_in_visible_member(request, family_id)
        # 포인트: edit 모달에서 현재 값을 채우기 위해 GET을 제공
        return Response(MemberFamilyMemberSerializer(obj).data)

    @transaction.atomic
    def patch(self, request, family_id: int, *args, **kwargs):
        obj = self._get_family_in_visible_member(request, family_id)
        ser = MemberFamilyMemberSerializer(instance=obj, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            ser.save()
        except DjangoValidationError as e:
            return Response({"detail": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MemberFamilyMemberSerializer(obj).data)

    def delete(self, request, family_id: int, *args, **kwargs):
        obj = self._get_family_in_visible_member(request, family_id)
        obj.delete()
        return Response({"ok": True})


class MemberVisitLogListCreateView(APIView):
    permission_classes = [IsPastoralRegistryStaff]

    def _get_visible_member(self, request, member_id: int) -> Member:
        qs = members_visible_to(request.user)
        try:
            return qs.get(pk=member_id)
        except Member.DoesNotExist as e:
            raise Http404("member not found") from e

    def get(self, request, member_id: int, *args, **kwargs):
        m = self._get_visible_member(request, member_id)
        visits = (
            MemberVisitLog.objects.filter(member=m)
            .select_related("recorded_by")
            .order_by("-visit_date", "-created_at")
        )
        return Response(MemberVisitLogSerializer(visits, many=True).data)

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @transaction.atomic
    def post(self, request, member_id: int, *args, **kwargs):
        m = self._get_visible_member(request, member_id)
        ser = MemberVisitLogSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            obj = ser.save(member=m, recorded_by=request.user)
        except DjangoValidationError as e:
            return Response({"detail": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MemberVisitLogSerializer(obj).data, status=status.HTTP_201_CREATED)


class MemberVisitLogDetailView(APIView):
    permission_classes = [IsPastoralRegistryStaff]

    def _get_visit_in_visible_member(
        self, request, visit_id: int
    ) -> MemberVisitLog:
        qs = members_visible_to(request.user)
        obj = MemberVisitLog.objects.select_related("member").filter(
            id=visit_id, member__in=qs
        ).first()
        if not obj:
            raise Http404("visit not found")
        return obj

    def get(self, request, visit_id: int, *args, **kwargs):
        obj = self._get_visit_in_visible_member(request, visit_id)
        return Response(MemberVisitLogSerializer(obj).data)

    @transaction.atomic
    def patch(self, request, visit_id: int, *args, **kwargs):
        obj = self._get_visit_in_visible_member(request, visit_id)
        ser = MemberVisitLogSerializer(instance=obj, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            ser.save()
        except DjangoValidationError as e:
            return Response({"detail": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MemberVisitLogSerializer(obj).data)

    def delete(self, request, visit_id: int, *args, **kwargs):
        obj = self._get_visit_in_visible_member(request, visit_id)
        obj.delete()
        return Response({"ok": True})


class MemberRoleOptionsView(APIView):
    """멤버 폼에서 사용할 직책(Role) 옵션 목록."""

    permission_classes = [IsPastoralRegistryStaff]

    def get(self, request, *args, **kwargs):
        roles = Role.objects.all().order_by("sort_order", "name")
        return Response(
            {
                "roles": [
                    {"id": r.id, "code": r.code, "name": r.name}
                    for r in roles
                ]
            }
        )

