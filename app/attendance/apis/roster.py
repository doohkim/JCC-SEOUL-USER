"""교적부(출석 명단) 입력용 API.

- midweek: 참석/온라인/불참(=없음은 불참) 3상태
- sunday: 각 멤버가 하루 중 선택한 예배 슬롯(부/인천/온라인/지교회) 1개만 가지며,
  "불참(아무것도 없음)"은 해당 멤버의 해당 날짜 출석 라인 삭제로 처리
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.apis.common import division_for_attendance_request
from attendance.choices import MidweekAttendanceStatus, MidweekServiceType, WorshipVenue
from attendance.models import MidweekAttendanceRecord, SundayAttendanceLine
from attendance.services.week_rollup import parse_week_rollup_key
from registry.models import MemberDivisionTeam
from users.models import Team


def _parse_week_sunday(week_sunday: str):
    try:
        return parse_week_rollup_key(week_sunday)
    except Http404:
        raise


def _midweek_service_date(week_sunday, service_type: str):
    # week_sunday is expected to be Sunday (weekday==6) via parse_week_rollup_key
    if service_type == MidweekServiceType.WEDNESDAY:
        return week_sunday - timedelta(days=4)
    if service_type == MidweekServiceType.SATURDAY:
        return week_sunday - timedelta(days=1)
    raise Http404("service_type must be wednesday|saturday")


def _normalize_hoejangdan_label(name: str) -> str:
    # display-only normalization: "부서 회장단" / "팀회장단" -> "회장단"
    s = (name or "").strip()
    compact = "".join(s.split())
    if compact in {"부서회장단", "팀회장단"}:
        return "회장단"
    return s


@dataclass(frozen=True)
class SundaySlot:
    key: str
    venue: str
    session_part: int
    branch_label: str = ""


SUNDAY_SLOT_BY_KEY: dict[str, SundaySlot] = {
    "absent": SundaySlot(key="absent", venue="", session_part=0),
    "seoul_1": SundaySlot(key="seoul_1", venue=WorshipVenue.SEOUL, session_part=1),
    "seoul_2": SundaySlot(key="seoul_2", venue=WorshipVenue.SEOUL, session_part=2),
    "seoul_3": SundaySlot(key="seoul_3", venue=WorshipVenue.SEOUL, session_part=3),
    "seoul_4": SundaySlot(key="seoul_4", venue=WorshipVenue.SEOUL, session_part=4),
    "incheon_1": SundaySlot(
        key="incheon_1", venue=WorshipVenue.INCHEON, session_part=1
    ),
    "incheon_2": SundaySlot(
        key="incheon_2", venue=WorshipVenue.INCHEON, session_part=2
    ),
    "incheon_3": SundaySlot(
        key="incheon_3", venue=WorshipVenue.INCHEON, session_part=3
    ),
    "incheon_4": SundaySlot(
        key="incheon_4", venue=WorshipVenue.INCHEON, session_part=4
    ),
    "online": SundaySlot(key="online", venue=WorshipVenue.ONLINE, session_part=0),
    "branch": SundaySlot(key="branch", venue=WorshipVenue.BRANCH, session_part=0),
}


def _sunday_slot_key_from_line(line: SundayAttendanceLine | None) -> str:
    if line is None:
        return "absent"
    venue = line.venue
    part = int(line.session_part or 0)
    if venue == WorshipVenue.ONLINE:
        return "online"
    if venue == WorshipVenue.BRANCH:
        return "branch"
    if venue == WorshipVenue.SEOUL:
        if part == 5:
            # legacy: "3·4부 연참"이 session_part=5로 들어간 데이터
            # UI에서는 연참을 없애고 3부로 표시한다.
            return "seoul_3"
        return f"seoul_{part}" if part in (1, 2, 3, 4) else "absent"
    if venue == WorshipVenue.INCHEON:
        if part == 5:
            # legacy: "3·4부 연참"이 session_part=5로 들어간 데이터
            # UI에서는 연참을 없애고 3부로 표시한다.
            return "incheon_3"
        return f"incheon_{part}" if part in (1, 2, 3, 4) else "absent"
    return "absent"


class AttendanceMidweekRosterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, week_sunday: str):
        division = division_for_attendance_request(request)
        ws = _parse_week_sunday(week_sunday)
        st = request.query_params.get("service_type") or ""
        if st not in dict(MidweekServiceType.choices):
            raise Http404("service_type is required: wednesday|saturday")

        service_date = _midweek_service_date(ws, st)
        qs = (
            MidweekAttendanceRecord.objects.filter(
                division=division,
                service_date=service_date,
                service_type=st,
            )
            .select_related("member", "team")
            .order_by("team_name_snapshot", "member__name")
        )

        # team_name_snapshot 그대로 저장값 기반(단, 화면 표시만 정규화)
        teams: dict[str, dict[str, Any]] = {}
        for r in qs:
            team_key = str(r.team_id or "") + "|" + (r.team_name_snapshot or "")
            display_name = _normalize_hoejangdan_label(r.team_name_snapshot or "")
            if team_key not in teams:
                teams[team_key] = {
                    "team_id": r.team_id,
                    "team_name": display_name or (r.team.name if r.team_id else ""),
                    "members": [],
                }
            teams[team_key]["members"].append(
                {
                    "record_id": r.id,
                    "member_id": r.member_id,
                    "member_name": r.member.name,
                    "status": r.status or MidweekAttendanceStatus.ABSENT,
                }
            )

        # stable ordering by team_name
        team_list = sorted(
            teams.values(), key=lambda t: (t["team_name"] or "", len(t["members"]))
        )
        return Response(
            {
                "mode": "midweek",
                "week_sunday": ws.isoformat(),
                "service_type": st,
                "service_date": service_date.isoformat(),
                "teams": team_list,
            }
        )

    @transaction.atomic
    def post(self, request, week_sunday: str):
        division = division_for_attendance_request(request)
        ws = _parse_week_sunday(week_sunday)
        payload = request.data or {}
        st = payload.get("service_type")
        if st not in dict(MidweekServiceType.choices):
            return Response({"error": "service_type is required"}, status=400)

        service_date = _midweek_service_date(ws, st)
        updates = payload.get("updates") or []
        if not isinstance(updates, list):
            return Response({"error": "updates must be a list"}, status=400)

        status_choices = {c[0] for c in MidweekAttendanceStatus.choices}

        # record_id 기반 업데이트 (권한/부서/일자 검증)
        record_ids = []
        for u in updates:
            try:
                record_ids.append(int(u.get("record_id")))
            except Exception:
                pass
        rec_map = {
            r.id: r
            for r in MidweekAttendanceRecord.objects.filter(
                division=division,
                service_date=service_date,
                service_type=st,
                id__in=record_ids,
            ).select_related("team")
        }

        changed = 0
        for u in updates:
            rid = u.get("record_id")
            st_value = u.get("status")
            if rid is None or st_value not in status_choices:
                continue
            rec = rec_map.get(int(rid))
            if not rec:
                continue
            if rec.status != st_value:
                rec.status = st_value
                rec.save(update_fields=["status"])
                changed += 1

        return Response({"ok": True, "changed": changed})


class AttendanceSundayRosterView(APIView):
    permission_classes = [IsAuthenticated]

    def _build_member_board(self, division, ws, member_ids: list[int]):
        # MemberDivisionTeam: 같은 멤버가 여러 팀이면 주 소속(is_primary) 우선 1개만 사용
        mdt_qs = (
            MemberDivisionTeam.objects.filter(
                division=division,
                team__isnull=False,
                member_id__in=member_ids,
            )
            .select_related("member", "team")
            .order_by("member_id", "-is_primary", "sort_order", "team_id")
        )

        chosen: dict[int, MemberDivisionTeam] = {}
        for mdt in mdt_qs:
            if mdt.member_id in chosen:
                continue
            chosen[mdt.member_id] = mdt

        member_ids_in_chosen = list(chosen.keys())
        lines_qs = (
            SundayAttendanceLine.objects.filter(
                division=division,
                service_date=ws,
                member_id__in=member_ids_in_chosen,
            )
            .order_by("member_id", "venue", "-session_part", "id")
            .select_related("member")
        )
        # member_id -> one line (deterministic first)
        by_member: dict[int, SundayAttendanceLine] = {}
        for line in lines_qs:
            if line.member_id not in by_member:
                by_member[line.member_id] = line

        teams: dict[int, dict[str, Any]] = {}
        for mid, mdt in chosen.items():
            team_id = mdt.team_id
            if team_id not in teams:
                teams[team_id] = {
                    "team_id": team_id,
                    "team_name": mdt.team.name if mdt.team_id else "",
                    "members": [],
                }
            teams[team_id]["members"].append(
                {
                    "member_id": mid,
                    "member_name": mdt.member.name,
                    "team_id": team_id,
                    "selection": _sunday_slot_key_from_line(by_member.get(mid)),
                }
            )

        # stable team ordering by team.sort_order (default 0)
        team_list = sorted(
            teams.values(),
            key=lambda t: (t["team_name"] or ""),
        )
        for t in team_list:
            t["members"].sort(key=lambda x: x["member_name"])
        return team_list

    def get(self, request, week_sunday: str):
        division = division_for_attendance_request(request)
        ws = _parse_week_sunday(week_sunday)

        # board members from 교적부: all members that have at least one Team in this division
        member_ids = list(
            MemberDivisionTeam.objects.filter(division=division, team__isnull=False).values_list(
                "member_id", flat=True
            )
            .distinct()
        )

        teams = self._build_member_board(division, ws, member_ids)
        return Response(
            {
                "mode": "sunday",
                "week_sunday": ws.isoformat(),
                "service_date": ws.isoformat(),
                "teams": teams,
            }
        )

    @transaction.atomic
    def post(self, request, week_sunday: str):
        division = division_for_attendance_request(request)
        ws = _parse_week_sunday(week_sunday)
        payload = request.data or {}

        updates = payload.get("updates") or []
        if not isinstance(updates, list):
            return Response({"error": "updates must be a list"}, status=400)

        allowed_keys = set(SUNDAY_SLOT_BY_KEY.keys())
        changed = 0

        # pre-collect member_ids
        member_ids = []
        for u in updates:
            try:
                member_ids.append(int(u.get("member_id")))
            except Exception:
                pass

        # ensure only members in division board can be updated
        board_member_ids = set(
            MemberDivisionTeam.objects.filter(
                division=division, team__isnull=False, member_id__in=member_ids
            ).values_list("member_id", flat=True)
        )

        for u in updates:
            member_id = u.get("member_id")
            selection = u.get("selection")
            team_id = u.get("team_id")
            if member_id is None or selection not in allowed_keys or member_id not in board_member_ids:
                continue

            team = None
            if selection != "absent" and team_id:
                team = Team.objects.filter(pk=team_id, division=division).first()

            # delete any existing lines for that member on the date (absent or re-slot)
            SundayAttendanceLine.objects.filter(
                division=division, service_date=ws, member_id=member_id
            ).delete()

            if selection == "absent":
                changed += 1
                continue

            slot = SUNDAY_SLOT_BY_KEY[selection]
            obj = SundayAttendanceLine(
                division=division,
                service_date=ws,
                member_id=member_id,
                venue=slot.venue,
                session_part=int(slot.session_part),
                branch_label=slot.branch_label or "",
                team=team,
                team_name_snapshot=(team.name if team else "")[:100] if team else "",
            )
            obj.full_clean()
            obj.save()
            changed += 1

        return Response({"ok": True, "changed": changed})

