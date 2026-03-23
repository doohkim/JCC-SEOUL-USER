"""
팀장(본인 팀만) 전용 출석 체크 API.

요구사항 반영:
- 주일예배: 여러 예배 슬롯 동시 선택(다중선택). 선택 없으면 미입력/불참 처리.
- 수요/토요예배: 참석/불참만 체크.
- 로그인 사용자는 본인 소속 팀 인원만 조회/수정 가능.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import Http404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.apis.common import division_for_attendance_request
from attendance.apis.roster import (
    SUNDAY_SLOT_BY_KEY,
    _midweek_service_date,
    _parse_week_sunday,
    _sunday_slot_key_from_line,
)
from attendance.choices import MidweekAttendanceStatus, MidweekServiceType, WorshipVenue
from attendance.models import MidweekAttendanceRecord, SundayAttendanceLine
from registry.models import MemberDivisionTeam
from users.models import Team


@dataclass(frozen=True)
class MemberBoardRow:
    member_id: int
    member_name: str
    team_id: int | None
    team_name: str


def _get_team_ids_for_division(request, division) -> list[int]:
    """
    로그인 사용자의 "본인 팀 범위"를 구합니다.

    - superuser: 해당 division 내 모든 팀 허용
    - 일반 사용자: division_teams 중 `team!=NULL`
      - `is_primary=True`가 있으면 그 팀만
      - 없으면 해당 division 내 팀 전체로 fallback
    """

    if request.user.is_superuser:
        return list(Team.objects.filter(division=division).values_list("id", flat=True))

    qs = request.user.division_teams.filter(division=division, team__isnull=False)
    team_ids = list(qs.filter(is_primary=True).values_list("team_id", flat=True).distinct())
    if not team_ids:
        team_ids = list(qs.values_list("team_id", flat=True).distinct())
    if not team_ids:
        raise PermissionDenied("팀장(관리) 권한이 없습니다.")
    return team_ids


def _build_member_board(*, division, allowed_team_ids: list[int]) -> list[MemberBoardRow]:
    """
    멤버가 여러 팀 소속일 수 있으므로, (is_primary 우선)으로 멤버당 대표 1팀을 선택합니다.
    """

    mdt_qs = (
        MemberDivisionTeam.objects.filter(
            division=division,
            team__isnull=False,
            member__is_active=True,
            team_id__in=allowed_team_ids,
        )
        .select_related("member", "team")
        .order_by("member_id", "-is_primary", "sort_order", "team_id")
    )

    chosen: dict[int, MemberDivisionTeam] = {}
    for mdt in mdt_qs:
        if mdt.member_id in chosen:
            continue
        chosen[mdt.member_id] = mdt

    rows: list[MemberBoardRow] = []
    for mid, mdt in chosen.items():
        rows.append(
            MemberBoardRow(
                member_id=mid,
                member_name=mdt.member.name,
                team_id=mdt.team_id,
                team_name=mdt.team.name if mdt.team_id else "",
            )
        )
    return rows


def _group_rows_by_team(rows: list[MemberBoardRow]) -> list[dict]:
    by_team: dict[int, list[MemberBoardRow]] = {}
    for r in rows:
        if r.team_id is None:
            continue
        by_team.setdefault(r.team_id, []).append(r)
    team_ids = sorted(by_team.keys())
    out: list[dict] = []
    for tid in team_ids:
        rs = by_team[tid]
        out.append(
            {
                "team_id": tid,
                "team_name": rs[0].team_name,
                "members": [
                    {"member_id": r.member_id, "member_name": r.member_name}
                    for r in sorted(rs, key=lambda x: x.member_name)
                ],
            }
        )
    return out


class AttendanceTeamSundayRosterView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_board(self, request, week_sunday: str):
        division = division_for_attendance_request(request)
        ws = _parse_week_sunday(week_sunday)
        allowed_team_ids = _get_team_ids_for_division(request, division)

        # 팀(허용 범위) + 멤버(대표 1행) 보드
        rows = _build_member_board(division=division, allowed_team_ids=allowed_team_ids)
        member_ids = [r.member_id for r in rows]
        if not member_ids:
            return division, ws, {}

        # 주일 출석 라인 → 선택 key set
        lines_qs = (
            SundayAttendanceLine.objects.filter(
                division=division, service_date=ws, member_id__in=member_ids
            )
            .select_related("member")
            .order_by("member_id", "venue", "-session_part", "id")
        )

        selections_by_member: dict[int, set[str]] = {mid: set() for mid in member_ids}
        has_any_line: dict[int, bool] = {mid: False for mid in member_ids}
        has_absent_marker: dict[int, bool] = {mid: False for mid in member_ids}
        for line in lines_qs:
            has_any_line[line.member_id] = True
            part = int(line.session_part or 0)
            # legacy: session_part=5(3·4부 연참)은 연참을 없애고 3부+4부로 풀어서 표시
            if line.venue in ("seoul", "incheon") and part == 5:
                if line.venue == "seoul":
                    selections_by_member[line.member_id].add("seoul_3")
                    selections_by_member[line.member_id].add("seoul_4")
                else:
                    selections_by_member[line.member_id].add("incheon_3")
                    selections_by_member[line.member_id].add("incheon_4")
                continue

            key = _sunday_slot_key_from_line(line)
            if key == "absent":
                has_absent_marker[line.member_id] = True
            elif key:
                selections_by_member[line.member_id].add(key)

        # 팀 묶기
        teams = _group_rows_by_team(rows)
        for t in teams:
            for m in t["members"]:
                mid = m["member_id"]
                if not has_any_line.get(mid, False):
                    m["entry_state"] = "unset"
                    m["selections"] = []
                elif selections_by_member.get(mid):
                    m["entry_state"] = "present"
                    m["selections"] = sorted(selections_by_member.get(mid, set()))
                else:
                    # 라인이 있는데 선택 키가 없으면 "불참" 마커로 취급
                    m["entry_state"] = "absent"
                    m["selections"] = []
        return division, ws, {"teams": teams}

    def get(self, request, week_sunday: str):
        division, ws, payload = self._get_board(request, week_sunday)
        return Response(
            {
                "mode": "team_sunday",
                "week_sunday": ws.isoformat(),
                "service_date": ws.isoformat(),
                "division_code": division.code,
                "teams": payload.get("teams", []),
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

        allowed_team_ids = _get_team_ids_for_division(request, division)
        rows = _build_member_board(division=division, allowed_team_ids=allowed_team_ids)
        member_ids_allowed = {r.member_id for r in rows}
        team_by_member = {r.member_id: r.team_id for r in rows}

        allowed_keys = set(SUNDAY_SLOT_BY_KEY.keys()) - {"absent"}
        allowed_entry_states = {"unset", "absent", "present"}

        changed = 0
        # 멤버별 요청 처리(다중선택은 라인들을 전부 재구성)
        for u in updates:
            try:
                member_id = int(u.get("member_id"))
            except Exception:
                continue

            if member_id not in member_ids_allowed:
                continue

            entry_state = (u.get("entry_state") or "").strip().lower()
            selections = u.get("selections") or []
            if not isinstance(selections, list):
                selections = [selections]
            selections = [str(s) for s in selections if s is not None]

            # backward compatibility: entry_state가 없으면 기존 방식으로 추정
            if entry_state not in allowed_entry_states:
                if "absent" in selections:
                    entry_state = "absent"
                elif selections:
                    entry_state = "present"
                else:
                    entry_state = "unset"

            if entry_state not in allowed_entry_states:
                continue

            # 기존 출석 행 제거(모드에 따라 재구성)
            existing_qs = SundayAttendanceLine.objects.filter(
                division=division, service_date=ws, member_id=member_id
            )
            before = existing_qs.count()
            if before:
                existing_qs.delete()
                changed += before

            team_id = team_by_member.get(member_id)
            team = (
                Team.objects.filter(pk=team_id, division=division).first()
                if team_id
                else None
            )
            team_snapshot = (team.name if team else "")[:100] if team else ""

            if entry_state == "unset":
                continue

            if entry_state == "absent":
                # 불참 마커: venue=서울, session_part=0 (UI에서 '불참'으로 표시)
                obj = SundayAttendanceLine(
                    division=division,
                    service_date=ws,
                    member_id=member_id,
                    venue=WorshipVenue.SEOUL,
                    session_part=0,
                    branch_label="",
                    team=team,
                    team_name_snapshot=team_snapshot,
                )
                obj.full_clean()
                obj.save()
                changed += 1
                continue

            # present 모드
            valid = [s for s in selections if s in allowed_keys]
            for key in valid:
                slot = SUNDAY_SLOT_BY_KEY[key]
                obj = SundayAttendanceLine(
                    division=division,
                    service_date=ws,
                    member_id=member_id,
                    venue=slot.venue,
                    session_part=int(slot.session_part or 0),
                    branch_label=slot.branch_label or "",
                    team=team,
                    team_name_snapshot=team_snapshot,
                )
                try:
                    obj.full_clean()
                    obj.save()
                except DjangoValidationError as e:
                    return Response(
                        {"error": "validation_failed", "detail": list(e.messages)},
                        status=400,
                    )
                changed += 1
            continue

        return Response({"ok": True, "changed": changed})


class AttendanceTeamMidweekRosterView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_board(self, request, week_sunday: str, service_type: str):
        division = division_for_attendance_request(request)
        ws = _parse_week_sunday(week_sunday)

        if service_type not in dict(MidweekServiceType.choices):
            raise Http404("service_type is required: wednesday|saturday")

        service_date = _midweek_service_date(ws, service_type)
        allowed_team_ids = _get_team_ids_for_division(request, division)
        rows = _build_member_board(division=division, allowed_team_ids=allowed_team_ids)
        member_ids = [r.member_id for r in rows]

        if not member_ids:
            return division, service_date, []

        # 기존 record만 조회 (없으면 미입력 → 불참 처리)
        rec_qs = (
            MidweekAttendanceRecord.objects.filter(
                division=division,
                service_date=service_date,
                service_type=service_type,
                member_id__in=member_ids,
            )
            .select_related("member", "team")
            .order_by("member_id", "-id")
        )

        rec_by_member: dict[int, MidweekAttendanceRecord] = {r.member_id: r for r in rec_qs}

        teams = _group_rows_by_team(rows)
        for t in teams:
            for m in t["members"]:
                rec = rec_by_member.get(m["member_id"])
                if not rec or not rec.status:
                    m["entry_state"] = "unset"
                    m["status"] = "absent"  # display placeholder
                    m["record_id"] = None
                else:
                    # 요구사항: 참석/불참만 보여줌. online은 참석으로 취급.
                    if rec.status in {MidweekAttendanceStatus.PRESENT, MidweekAttendanceStatus.ONLINE}:
                        m["entry_state"] = "present"
                        m["status"] = "present"
                    else:
                        m["entry_state"] = "absent"
                        m["status"] = "absent"
                    m["record_id"] = rec.id
        return division, service_date, teams

    def get(self, request, week_sunday: str):
        service_type = request.query_params.get("service_type") or ""
        division, service_date, teams = self._get_board(request, week_sunday, service_type)
        return Response(
            {
                "mode": "team_midweek",
                "week_sunday": service_date.isoformat(),
                "service_date": service_date.isoformat(),
                "division_code": division.code,
                "service_type": service_type,
                "teams": teams,
            }
        )

    @transaction.atomic
    def post(self, request, week_sunday: str):
        service_type = request.query_params.get("service_type") or ""
        if service_type not in dict(MidweekServiceType.choices):
            raise Http404("service_type is required: wednesday|saturday")

        division = division_for_attendance_request(request)
        ws = _parse_week_sunday(week_sunday)
        service_date = _midweek_service_date(ws, service_type)

        payload = request.data or {}
        updates = payload.get("updates") or []
        if not isinstance(updates, list):
            return Response({"error": "updates must be a list"}, status=400)

        allowed_team_ids = _get_team_ids_for_division(request, division)
        rows = _build_member_board(division=division, allowed_team_ids=allowed_team_ids)
        member_ids_allowed = {r.member_id for r in rows}
        team_by_member = {r.member_id: r.team_id for r in rows}

        valid_status = {"present", "absent", "unset"}
        changed = 0

        # record 미리 조회
        update_member_ids = []
        for u in updates:
            try:
                mid = int(u.get("member_id"))
                update_member_ids.append(mid)
            except Exception:
                pass
        update_member_ids = [mid for mid in update_member_ids if mid in member_ids_allowed]

        rec_qs = MidweekAttendanceRecord.objects.filter(
            division=division,
            service_date=service_date,
            service_type=service_type,
            member_id__in=update_member_ids,
        ).select_related("team")
        rec_by_member = {r.member_id: r for r in rec_qs}

        for u in updates:
            try:
                member_id = int(u.get("member_id"))
            except Exception:
                continue
            if member_id not in member_ids_allowed:
                continue

            status_key = (u.get("status") or "").strip().lower()
            if status_key not in valid_status:
                continue

            rec = rec_by_member.get(member_id)
            team_id = team_by_member.get(member_id)
            team = (
                Team.objects.filter(pk=team_id, division=division).first() if team_id else None
            )

            if status_key == "unset":
                if rec:
                    rec.delete()
                    changed += 1
                continue

            desired = (
                MidweekAttendanceStatus.PRESENT
                if status_key == "present"
                else MidweekAttendanceStatus.ABSENT
            )

            if rec:
                prev_status = rec.status
                prev_team_id = rec.team_id
                prev_snapshot = rec.team_name_snapshot

                new_snapshot = (team.name if team else "")[:100] if team else ""

                if rec.status != desired:
                    rec.status = desired
                if rec.team_id != (team.id if team else None):
                    rec.team = team
                if rec.team_name_snapshot != new_snapshot:
                    rec.team_name_snapshot = new_snapshot

                if (
                    prev_status != rec.status
                    or prev_team_id != rec.team_id
                    or prev_snapshot != rec.team_name_snapshot
                ):
                    rec.save(update_fields=["status", "team", "team_name_snapshot"])
                    changed += 1
            else:
                obj = MidweekAttendanceRecord(
                    division=division,
                    service_date=service_date,
                    service_type=service_type,
                    member_id=member_id,
                    team=team,
                    team_name_snapshot=(team.name if team else "")[:100] if team else "",
                    status=desired,
                )
                obj.full_clean()
                obj.save()
                changed += 1

        return Response({"ok": True, "changed": changed})

