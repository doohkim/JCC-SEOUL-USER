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
    RetreatCouncilMembership,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatPickup,
    RetreatPickupLocation,
    RetreatSession,
    RetreatSessionAttendee,
    RetreatStaffApplication,
    RetreatTimetableEntry,
)
from users.models import User


STATUS_LABELS = {
    "present": "참석",
    "absent": "결석",
    "pending": "검토 중",
    "approved": "승인",
    "rejected": "반려",
}
CHECK_IN_LABELS = {
    "checked_in": "입실",
    "checked_out": "퇴실",
    "pending": "입실전",
}
PICKUP_DIRECTION_LABELS = {
    "arrival": "입회",
    "departure": "출회",
}
PARTICIPATION_LABELS = {
    "participating": "참석",
    "absent": "불참",
}
LODGING_STAY_LABELS = {
    "active": "숙박 중",
    "unassigned": "미배정",
    "ended": "숙박 종료",
    "no_stay": "숙박 안 함",
    "absent": "불참",
}
ROLE_LABELS = {
    "event_admin": "집회 전체 관리자",
    "event_observer": "집회 전체 관찰자",
    "region_admin": "지역 관리자",
    "region_observer": "지역 관찰자",
    "division_admin": "부서 관리자",
    "division_observer": "부서 관찰자",
    "pickup_observer": "픽업 관찰자",
    "member": "조원",
    "leader": "조장",
    "vice_leader": "부조장",
    "teacher": "선생님",
}
GENDER_LABELS = {"male": "남성", "female": "여성"}
INTERNAL_DETAIL_KEYS = frozenset(
    {
        "id",
        "updated_at",
        "user_id",
        "group_id",
        "region_id",
        "division_id",
        "staff",
        "username",
        "source",
        "user",
        "group",
        "region",
        "division",
        "reviewed_by",
        "reviewed_at",
        "application_track",
        "applicant_name",
        "number",
        "event_id",
        "extra_scopes",
        "order",
        "sort_order",
        "check_in_status_manually_set",
        "lodging_room_id",
    }
)
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
    "rejection_reason": "반려 사유",
    "group_role": "조 역할",
    "approved_council_role": "집회 운영 역할",
    "member_role": "조 역할",
    "lodging_stay_status": "숙박 상태",
    "boarding_place": "탑승장소",
    "contact": "연락처",
    "direction": "구분",
    "train_time": "이동 시각",
}

DATETIME_FIELD_KEYS = frozenset(
    {
        "expected_check_in_at",
        "expected_check_out_at",
        "checked_in_at",
        "checked_out_at",
        "occurs_at",
        "train_time",
    }
)


@dataclass(frozen=True)
class HumanizedLog:
    log: RetreatChangeLog
    actor: str
    summary: str
    detail: list[str]
    target_label: str
    action_label: str


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
    elif log.target_type == RetreatChangeLog.TargetType.STAFF_APPLICATION:
        summary = _staff_application_summary(log, ctx, before, after)
    elif log.target_type == RetreatChangeLog.TargetType.PICKUP:
        summary = _pickup_summary(log, ctx, before, after)
    elif log.target_type == RetreatChangeLog.TargetType.GROUP:
        summary = _group_summary(log, ctx, before, after)
    elif log.target_type == RetreatChangeLog.TargetType.PICKUP_LOCATION:
        summary = _pickup_location_summary(log, ctx, before, after)
    elif log.target_type == RetreatChangeLog.TargetType.TIMETABLE:
        summary = _timetable_summary(log, ctx, before, after)
    else:
        summary = (
            f"{log.get_target_type_display()}의 변경 내용을 기록했습니다. "
            "대상 이름은 확인할 수 없습니다."
        )

    subject = "시스템이" if actor == "시스템 자동" else f"{actor}님이"
    return HumanizedLog(
        log=log,
        actor=actor,
        summary=f"{subject} {summary}",
        detail=_human_detail(log, before, after),
        target_label=_target_label(log, before, after),
        action_label=_action_label(log, before, after),
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
    council_ids = [
        l.target_id
        for l in logs
        if l.target_type == RetreatChangeLog.TargetType.GROUP_MEMBERSHIP
        and bool((l.payload_after or l.payload_before or {}).get("staff"))
    ]
    application_ids = [
        l.target_id
        for l in logs
        if l.target_type == RetreatChangeLog.TargetType.STAFF_APPLICATION
    ]
    pickup_ids = [
        l.target_id for l in logs if l.target_type == RetreatChangeLog.TargetType.PICKUP
    ]
    group_target_ids = [
        l.target_id for l in logs if l.target_type == RetreatChangeLog.TargetType.GROUP
    ]
    referenced_group_ids = {
        int(data["group_id"])
        for log in logs
        for data in (log.payload_before or {}, log.payload_after or {})
        if str(data.get("group_id") or "").isdigit()
    }
    location_ids = [
        l.target_id
        for l in logs
        if l.target_type == RetreatChangeLog.TargetType.PICKUP_LOCATION
    ]
    timetable_ids = [
        l.target_id
        for l in logs
        if l.target_type == RetreatChangeLog.TargetType.TIMETABLE
    ]
    user_ids = {
        int(data.get("user_id") or data.get("user"))
        for log in logs
        for data in (log.payload_before or {}, log.payload_after or {})
        if str(data.get("user_id") or data.get("user") or "").isdigit()
    }
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
        "council": {
            x.id: x
            for x in RetreatCouncilMembership.objects.filter(
                pk__in=council_ids
            ).select_related("user", "user__profile", "region", "division")
        },
        "users": {
            x.id: x
            for x in User.objects.filter(pk__in=user_ids).select_related("profile")
        },
        "staff_application": {
            x.id: x
            for x in RetreatStaffApplication.objects.filter(
                pk__in=application_ids
            ).select_related(
                "user",
                "user__profile",
                "region",
                "division",
                "group",
            )
        },
        "pickup": {
            x.id: x
            for x in RetreatPickup.objects.filter(pk__in=pickup_ids).select_related(
                "group",
                "region",
                "division",
            )
        },
        "groups": {
            x.id: x
            for x in RetreatGroup.objects.filter(
                pk__in=set(group_target_ids) | referenced_group_ids
            ).select_related("region", "division")
        },
        "pickup_location": {
            x.id: x for x in RetreatPickupLocation.objects.filter(pk__in=location_ids)
        },
        "timetable": {
            x.id: x for x in RetreatTimetableEntry.objects.filter(pk__in=timetable_ids)
        },
    }


def _actor_name(log: RetreatChangeLog) -> str:
    user = log.changed_by
    if not user:
        return "시스템 자동"
    profile = getattr(user, "profile", None)
    display = (
        getattr(profile, "real_name", "") or getattr(profile, "display_name", "") or ""
    ).strip()
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
    data = after or before
    if data.get("staff"):
        return _council_membership_summary(log, ctx, before, after)

    membership = ctx["membership"].get(log.target_id)
    user = getattr(membership, "user", None) or ctx["users"].get(data.get("user_id"))
    user_name = _user_name(user, data)
    group_name = (
        getattr(getattr(membership, "group", None), "name", "")
        or getattr(ctx["groups"].get(data.get("group_id")), "name", "")
        or data.get("group_name")
        or "조"
    )
    role = data.get("role_display") or _role(data.get("role")) or "운영진"
    if log.action == RetreatChangeLog.Action.CREATE:
        return f"{user_name}님을 {group_name}의 {role} 역할로 지정했습니다."
    if log.action == RetreatChangeLog.Action.DELETE:
        return f"{user_name}님의 {group_name} 운영 권한을 해제했습니다."
    old_role = _role(before.get("role"))
    new_role = _role(after.get("role"))
    if old_role and new_role and old_role != new_role:
        return (
            f"{user_name}님의 {group_name} 역할을 "
            f"{old_role}에서 {new_role} 역할로 변경했습니다."
        )
    return f"{user_name}님의 {group_name} 운영진 정보를 수정했습니다."


def _council_membership_summary(log, ctx, before, after) -> str:
    data = after or before
    membership = ctx["council"].get(log.target_id)
    user = getattr(membership, "user", None) or ctx["users"].get(data.get("user_id"))
    user_name = _user_name(user, data)
    old_role = _role(before.get("role"))
    new_role = _role(after.get("role") or getattr(membership, "role", ""))
    scope = _council_scope(membership, data)

    if log.action == RetreatChangeLog.Action.CREATE:
        return (
            f"{user_name}님에게 "
            f"{scope}{new_role or '집회 운영진'} 권한을 부여했습니다."
        )
    if log.action == RetreatChangeLog.Action.DELETE:
        return f"{user_name}님의 집회 운영 권한을 해제했습니다."
    if old_role and new_role and old_role != new_role:
        return (
            f"{user_name}님의 집회 운영 권한을 "
            f"{old_role}에서 {new_role} 역할로 변경했습니다."
        )
    if new_role:
        return f"{user_name}님의 집회 운영 권한을 {scope}{new_role}로 설정했습니다."
    return f"{user_name}님의 집회 운영진 정보를 수정했습니다."


def _user_name(user, payload: dict) -> str:
    profile = getattr(user, "profile", None)
    return (
        (getattr(profile, "real_name", "") or "").strip()
        or (getattr(profile, "display_name", "") or "").strip()
        or getattr(user, "username", "")
        or payload.get("username")
        or "이름을 확인할 수 없는 사용자"
    )


def _council_scope(membership, payload: dict) -> str:
    division = getattr(membership, "division", None)
    region = getattr(membership, "region", None)
    if division:
        return f"{division.region.name} · {division.name} "
    if region:
        return f"{region.name} "
    return ""


def _staff_application_summary(log, ctx, before, after) -> str:
    data = after or before
    application = ctx["staff_application"].get(log.target_id)
    user_id = (
        getattr(application, "user_id", None)
        or data.get("user_id")
        or data.get("user")
        or before.get("user_id")
        or before.get("user")
    )
    user = getattr(application, "user", None) or ctx["users"].get(user_id)
    user_name = _user_name(user, data)
    track_code = (
        getattr(application, "application_track", "")
        or data.get("application_track")
        or before.get("application_track")
    )
    track = {
        "council": "집회 운영진",
        "group_leadership": "조 운영진",
    }.get(track_code, "운영진")

    if log.action == RetreatChangeLog.Action.APPROVE:
        assignment = _staff_application_assignment(application, after)
        suffix = f" ({assignment})" if assignment else ""
        return f"{user_name}님의 {track} 신청을 승인했습니다.{suffix}"
    if log.action == RetreatChangeLog.Action.REJECT:
        reason = after.get("rejection_reason") or ""
        suffix = f" 반려 사유: {reason}" if reason else ""
        return f"{user_name}님의 {track} 신청을 반려했습니다.{suffix}"
    if log.action == RetreatChangeLog.Action.DELETE:
        return f"{user_name}님의 승인된 운영진 신청 기록을 삭제했습니다."
    if log.action == RetreatChangeLog.Action.CREATE:
        return f"{user_name}님이 {track}으로 신청했습니다."
    return f"{user_name}님의 {track} 신청 정보를 수정했습니다."


def _staff_application_assignment(application, payload: dict) -> str:
    group = getattr(application, "group", None)
    group_name = getattr(group, "name", "")
    group_role = _role(
        getattr(application, "group_role", "") or payload.get("group_role")
    )
    council_role = _role(
        getattr(application, "approved_council_role", "")
        or payload.get("approved_council_role")
    )
    if group_name and group_role:
        return f"{group_name} · {group_role}"
    return council_role


def _pickup_summary(log, ctx, before, after) -> str:
    data = after or before
    pickup = ctx["pickup"].get(log.target_id)
    name = getattr(pickup, "name", "") or data.get("name") or "이름 미확인 조원"
    direction_code = (
        getattr(pickup, "direction", "")
        or data.get("direction")
        or before.get("direction")
    )
    direction = PICKUP_DIRECTION_LABELS.get(direction_code, "차량")
    place = getattr(pickup, "boarding_place", "") or data.get("boarding_place") or ""
    place_suffix = f" ({place})" if place else ""

    if log.action == RetreatChangeLog.Action.CREATE:
        return f"{name}님의 {direction} 픽업 신청을 등록했습니다.{place_suffix}"
    if log.action == RetreatChangeLog.Action.DELETE:
        return f"{name}님의 {direction} 픽업 신청을 삭제했습니다.{place_suffix}"
    if log.action == RetreatChangeLog.Action.UPDATE:
        return f"{name}님의 {direction} 픽업 정보를 수정했습니다."
    return f"{name}님의 {direction} 픽업 정보를 변경했습니다."


def _group_summary(log, ctx, before, after) -> str:
    data = after or before
    group = ctx["groups"].get(log.target_id)
    name = getattr(group, "name", "") or data.get("name") or "이름 미확인 조"
    if log.action == RetreatChangeLog.Action.CREATE:
        return f"{name}를 새로 만들었습니다."
    if log.action == RetreatChangeLog.Action.DELETE:
        return f"{name}를 삭제했습니다."
    old_name = before.get("name")
    new_name = after.get("name")
    if old_name and new_name and old_name != new_name:
        return f"{old_name}의 이름을 {new_name}(으)로 변경했습니다."
    return f"{name}의 지역·부서 또는 기본 정보를 수정했습니다."


def _pickup_location_summary(log, ctx, before, after) -> str:
    data = after or before
    location = ctx["pickup_location"].get(log.target_id)
    name = getattr(location, "name", "") or data.get("name") or "이름 미확인 장소"
    if log.action == RetreatChangeLog.Action.CREATE:
        return f"픽업 탑승장소 {name}을 추가했습니다."
    if log.action == RetreatChangeLog.Action.DELETE:
        return f"픽업 탑승장소 {name}을 삭제했습니다."
    old_name = before.get("name")
    new_name = after.get("name")
    if old_name and new_name and old_name != new_name:
        return f"픽업 탑승장소를 {old_name}에서 {new_name}(으)로 변경했습니다."
    return f"픽업 탑승장소 {name}의 정보를 수정했습니다."


def _timetable_summary(log, ctx, before, after) -> str:
    data = after or before
    entry = ctx["timetable"].get(log.target_id)
    title = getattr(entry, "title", "") or data.get("title") or "이름 미확인 일정"
    if log.action == RetreatChangeLog.Action.CREATE:
        return f"타임테이블에 「{title}」 일정을 추가했습니다."
    if log.action == RetreatChangeLog.Action.DELETE:
        return f"타임테이블에서 「{title}」 일정을 삭제했습니다."
    old_title = before.get("title")
    new_title = after.get("title")
    if old_title and new_title and old_title != new_title:
        return f"「{old_title}」 일정을 「{new_title}」 일정으로 변경했습니다."
    return f"타임테이블 「{title}」 일정을 수정했습니다."


def _target_label(log, before: dict, after: dict) -> str:
    data = after or before
    if log.target_type == RetreatChangeLog.TargetType.GROUP_MEMBERSHIP and data.get(
        "staff"
    ):
        return "집회 운영진"
    return log.get_target_type_display()


def _action_label(log, before: dict, after: dict) -> str:
    if log.target_type == RetreatChangeLog.TargetType.GROUP_MEMBERSHIP:
        return {
            RetreatChangeLog.Action.CREATE: "권한 지정",
            RetreatChangeLog.Action.UPDATE: "권한 변경",
            RetreatChangeLog.Action.DELETE: "권한 해제",
        }.get(log.action, log.get_action_display())
    return log.get_action_display()


def _human_detail(log, before: dict, after: dict) -> list[str]:
    if (
        log.target_type == RetreatChangeLog.TargetType.PICKUP
        and log.action == RetreatChangeLog.Action.DELETE
    ):
        lines = []
        for key in ("boarding_place", "train_time", "contact", "note"):
            value = before.get(key)
            if value in (None, ""):
                continue
            lines.append(f"{FIELD_LABELS.get(key, key)}: {_format_value(key, value)}")
        return lines
    return _diff_lines(before, after)


def _diff_lines(before: dict, after: dict) -> list[str]:
    if not before and not after:
        return []
    keys = sorted((set(before) | set(after)) - INTERNAL_DETAIL_KEYS)
    out = []
    for key in keys:
        old = before.get(key)
        new = after.get(key)
        if old == new:
            continue
        label = FIELD_LABELS.get(key, key)
        old_display = _format_value(key, old)
        new_display = _format_value(key, new)
        if old_display == new_display:
            continue
        out.append(f"{label}: {old_display} → {new_display}")
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
    if key == "lodging_stay_status":
        return LODGING_STAY_LABELS.get(value, str(value or "-"))
    if key == "direction":
        return PICKUP_DIRECTION_LABELS.get(value, str(value or "-"))
    if key in {"role", "member_role", "group_role", "approved_council_role"}:
        return _role(value)
    if key == "gender":
        return GENDER_LABELS.get(value, str(value or "-"))
    if isinstance(value, bool):
        return "예" if value else "아니요"
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


def _role(value) -> str:
    if value in (None, ""):
        return ""
    return ROLE_LABELS.get(value, str(value))


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
