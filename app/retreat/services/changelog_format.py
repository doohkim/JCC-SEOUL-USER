"""수련회 변경 이력을 사람이 읽기 쉬운 문장으로 변환."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatChangeLog,
    RetreatGroupMembership,
    RetreatSession,
    RetreatSessionAttendee,
)


STATUS_LABELS = {
    "present": "참석",
    "absent": "결석",
}
CHECK_IN_LABELS = {
    "checked_in": "입실",
    "checked_out": "퇴실",
    "pending": "입실전",
}
PARTICIPATION_LABELS = {
    "participating": "참석",
    "absent": "불참",
}
FIELD_LABELS = {
    "name": "이름",
    "phone": "연락처",
    "gender": "성별",
    "memo": "메모",
    "participation_status": "참석 여부",
    "check_in_status": "입·퇴실",
    "expected_check_in_at": "예상 입실 시각",
    "expected_check_out_at": "예상 퇴실 시각",
    "checked_in_at": "실제 입실 시각",
    "checked_out_at": "실제 퇴실 시각",
    "status": "상태",
    "note": "메모",
    "role": "역할",
    "location": "장소",
    "sequence": "순서",
    "occurs_at": "진행 일시",
    "title": "프로그램명",
    "day": "일자",
    "start_time": "시작 시각",
    "end_day": "종료 일자",
    "end_time": "종료 시각",
}

DATETIME_FIELD_KEYS = frozenset(
    {
        "expected_check_in_at",
        "expected_check_out_at",
        "checked_in_at",
        "checked_out_at",
        "occurs_at",
    }
)


@dataclass(frozen=True)
class HumanizedLog:
    log: RetreatChangeLog
    actor: str
    summary: str
    detail: list[str]


def humanize_change_logs(logs: Iterable[RetreatChangeLog]) -> list[HumanizedLog]:
    log_list = list(logs)
    ctx = _build_context(log_list)
    return [humanize_change_log(log, ctx) for log in log_list]


def humanize_change_log(log: RetreatChangeLog, ctx: dict | None = None) -> HumanizedLog:
    ctx = ctx or _build_context([log])
    actor = _actor_name(log)
    before = log.payload_before or {}
    after = log.payload_after or {}

    if log.target_type == RetreatChangeLog.TargetType.ATTENDANCE:
        summary = _attendance_summary(log, ctx, before, after)
    elif log.target_type == RetreatChangeLog.TargetType.ATTENDEE:
        summary = _attendee_summary(log, ctx, before, after)
    elif log.target_type == RetreatChangeLog.TargetType.ENROLLMENT:
        summary = _enrollment_summary(log, ctx, before, after)
    elif log.target_type == RetreatChangeLog.TargetType.SESSION:
        summary = _session_summary(log, ctx, before, after)
    elif log.target_type == RetreatChangeLog.TargetType.GROUP_MEMBERSHIP:
        summary = _group_membership_summary(log, ctx, before, after)
    else:
        summary = f"{log.get_target_type_display()} #{log.target_id} {log.get_action_display()}"

    return HumanizedLog(
        log=log,
        actor=actor,
        summary=summary,
        detail=_diff_lines(before, after),
    )


def _build_context(logs: list[RetreatChangeLog]) -> dict:
    attendance_ids = [
        l.target_id
        for l in logs
        if l.target_type == RetreatChangeLog.TargetType.ATTENDANCE
    ]
    attendee_ids = [
        l.target_id
        for l in logs
        if l.target_type == RetreatChangeLog.TargetType.ATTENDEE
    ]
    enrollment_ids = [
        l.target_id
        for l in logs
        if l.target_type == RetreatChangeLog.TargetType.ENROLLMENT
    ]
    session_ids = [
        l.target_id
        for l in logs
        if l.target_type == RetreatChangeLog.TargetType.SESSION
    ]
    membership_ids = [
        l.target_id
        for l in logs
        if l.target_type == RetreatChangeLog.TargetType.GROUP_MEMBERSHIP
    ]
    return {
        "attendance": {
            x.id: x
            for x in RetreatAttendance.objects.filter(
                pk__in=attendance_ids
            ).select_related(
                "enrollment",
                "enrollment__session",
                "enrollment__source_group",
            )
        },
        "attendee": {
            x.id: x
            for x in RetreatAttendee.objects.filter(pk__in=attendee_ids).select_related(
                "group", "group__region", "group__division"
            )
        },
        "enrollment": {
            x.id: x
            for x in RetreatSessionAttendee.objects.filter(
                pk__in=enrollment_ids
            ).select_related("session", "source_group")
        },
        "session": {x.id: x for x in RetreatSession.objects.filter(pk__in=session_ids)},
        "membership": {
            x.id: x
            for x in RetreatGroupMembership.objects.filter(
                pk__in=membership_ids
            ).select_related("user", "user__profile", "group")
        },
    }


def _actor_name(log: RetreatChangeLog) -> str:
    user = log.changed_by
    if not user:
        return "시스템 자동"
    profile = getattr(user, "profile", None)
    display = (getattr(profile, "display_name", "") or "").strip()
    return display or user.get_username()


def _attendance_summary(log, ctx, before, after) -> str:
    attendance = ctx["attendance"].get(log.target_id)
    enrollment = getattr(attendance, "enrollment", None)
    session_name = (
        getattr(getattr(enrollment, "session", None), "name", "")
        or _session_name_from_payload(ctx, after or before)
        or f"출석부 #{(after or before).get('session_id', '-')}"
    )
    attendee_name = (
        getattr(enrollment, "name", "")
        or after.get("name")
        or before.get("name")
        or f"조원 #{(after or before).get('attendee_id', '-')}"
    )
    group_name = getattr(enrollment, "group_name", "") or after.get("group_name") or ""
    target = f"{attendee_name}({group_name})" if group_name else attendee_name
    new_status = _status(after.get("status"))
    old_status = _status(before.get("status"))
    if log.action == RetreatChangeLog.Action.CREATE:
        suffix = " · 자동 결석" if _is_auto_absent(after) else ""
        return f"출석부 「{session_name}」에서 {target} {new_status}{suffix}"
    return f"출석부 「{session_name}」에서 {target} {old_status} → {new_status}"


def _attendee_summary(log, ctx, before, after) -> str:
    data = after or before
    attendee = ctx["attendee"].get(log.target_id)
    name = getattr(attendee, "name", "") or data.get("name") or f"조원 #{log.target_id}"
    place = _place_from_attendee(attendee) or _place_from_payload(data)
    check_in = _check_in(data.get("check_in_status"))
    if log.action == RetreatChangeLog.Action.CREATE:
        return f"조원 {name} 추가 ({place}, {check_in})"
    if log.action == RetreatChangeLog.Action.DELETE:
        return f"조원 {name} 삭제 (과거 출석 기록은 보존)"
    diffs = "; ".join(_diff_lines(before, after)) or "내용 변경"
    return f"조원 {name} 수정: {diffs}"


def _enrollment_summary(log, ctx, before, after) -> str:
    data = after or before
    enrollment = ctx["enrollment"].get(log.target_id)
    session_name = getattr(
        getattr(enrollment, "session", None), "name", ""
    ) or _session_name_from_payload(ctx, data)
    name = (
        getattr(enrollment, "name", "") or data.get("name") or f"조원 #{log.target_id}"
    )
    group_name = getattr(enrollment, "group_name", "") or data.get("group_name") or ""
    reason = (
        "진행중 출석부 자동 합류"
        if data.get("auto_join_active_session")
        else "출석부 명단 스냅샷"
    )
    return f"출석부 「{session_name}」에 {name}({group_name}) {reason}"


def _session_summary(log, ctx, before, after) -> str:
    session = ctx["session"].get(log.target_id)
    name = (
        getattr(session, "name", "")
        or after.get("name")
        or before.get("name")
        or f"#{log.target_id}"
    )
    if before.get("status") != after.get("status"):
        if after.get("status") == "closed":
            return f"출석부 「{name}」 마감"
        if after.get("status") == "active":
            return f"출석부 「{name}」 재오픈"
    if log.action == RetreatChangeLog.Action.CREATE:
        return f"출석부 「{name}」 생성"
    if log.action == RetreatChangeLog.Action.DELETE:
        return f"출석부 「{name}」 삭제"
    diffs = "; ".join(_diff_lines(before, after)) or "내용 변경"
    return f"출석부 「{name}」 수정: {diffs}"


def _group_membership_summary(log, ctx, before, after) -> str:
    membership = ctx["membership"].get(log.target_id)
    data = after or before
    user = getattr(membership, "user", None)
    profile = getattr(user, "profile", None)
    user_name = (
        (getattr(profile, "display_name", "") or "").strip()
        or getattr(user, "username", "")
        or data.get("username")
        or f"사용자 #{data.get('user_id', '-')}"
    )
    group_name = (
        getattr(getattr(membership, "group", None), "name", "")
        or data.get("group_name")
        or "조"
    )
    role = data.get("role_display") or data.get("role") or "운영진"
    if log.action == RetreatChangeLog.Action.CREATE:
        return f"{user_name}을 {group_name} {role}로 추가"
    if log.action == RetreatChangeLog.Action.DELETE:
        return f"{user_name}을 {group_name} 운영진에서 제거"
    diffs = "; ".join(_diff_lines(before, after)) or "역할 변경"
    return f"{user_name} {group_name} 운영진 수정: {diffs}"


def _diff_lines(before: dict, after: dict) -> list[str]:
    if not before and not after:
        return []
    keys = sorted((set(before) | set(after)) - {"id", "updated_at"})
    out = []
    for key in keys:
        old = before.get(key)
        new = after.get(key)
        if old == new:
            continue
        label = FIELD_LABELS.get(key, key)
        out.append(f"{label}: {_format_value(key, old)} → {_format_value(key, new)}")
    return out


def _format_value(key: str, value) -> str:
    if value in (None, ""):
        return "-"
    if key == "status":
        return _status(value)
    if key == "check_in_status":
        return _check_in(value)
    if key == "participation_status":
        return PARTICIPATION_LABELS.get(value, str(value or "-"))
    if key in DATETIME_FIELD_KEYS or key.endswith("_at"):
        return _format_datetime_value(value)
    return str(value)


def _format_datetime_value(value) -> str:
    if value in (None, ""):
        return "-"
    dt = value
    if isinstance(value, str):
        dt = parse_datetime(value.strip())
        if dt is None:
            return value.strip()
    if not hasattr(dt, "year"):
        return str(value)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_default_timezone())
    return timezone.localtime(dt).strftime("%Y.%m.%d %H:%M")


def _status(value) -> str:
    return STATUS_LABELS.get(value, str(value or "-"))


def _check_in(value) -> str:
    return CHECK_IN_LABELS.get(value, str(value or "-"))


def _place_from_attendee(attendee) -> str:
    if not attendee:
        return "-"
    group = getattr(attendee, "group", None)
    if not group:
        return "-"
    return f"{group.region.name} · {group.division.name} · {group.name}"


def _place_from_payload(payload: dict) -> str:
    region = payload.get("region_name") or ""
    division = payload.get("division_name") or ""
    group = payload.get("group_name") or ""
    return " · ".join([x for x in (region, division, group) if x]) or "-"


def _session_name_from_payload(ctx: dict, payload: dict) -> str:
    sid = payload.get("session_id")
    session = ctx.get("session", {}).get(sid)
    return getattr(session, "name", "") if session else ""


def _is_auto_absent(payload: dict) -> bool:
    return bool(
        payload.get("auto_default_for_checked_out")
        or payload.get("auto_default_for_pending")
        or payload.get("auto_default_for_late_added_attendee")
    )
