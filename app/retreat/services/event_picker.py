"""집회 드롭다운 — 활성 목록·기본 선택·탭별 URL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse

from retreat.models import RetreatEvent
from retreat.services.staff_application import (
    event_staff_status,
    has_retreat_operational_access,
    user_assigned_to_event,
)

SESSION_LAST_RETREAT_EVENT_ID = "retreat_last_event_id"

if TYPE_CHECKING:
    from users.models import User


def active_retreat_events() -> list[RetreatEvent]:
    """활성 집회 전체 (RetreatEvent.Meta.ordering 적용)."""
    return list(RetreatEvent.objects.filter(is_active=True))


def default_retreat_event_for(user: User) -> RetreatEvent | None:
    """수련회 탭 기본 집회 — 운영 권한 → 배정 → 날짜순 첫 활성."""
    events = active_retreat_events()
    for event in events:
        if has_retreat_operational_access(user, event):
            return event
    for event in events:
        if user_assigned_to_event(user, event):
            return event
    return events[0] if events else None


def set_last_retreat_event(session, event_id: int) -> None:
    """마지막으로 본 수련회 집회를 세션에 저장."""
    session[SESSION_LAST_RETREAT_EVENT_ID] = int(event_id)
    if hasattr(session, "modified"):
        session.modified = True


def event_recallable_for_user(user: User, event: RetreatEvent) -> bool:
    """세션 복원 시 해당 집회로 다시내도 되는지."""
    if not event.is_active:
        return False
    if has_retreat_operational_access(user, event):
        return True
    if user_assigned_to_event(user, event):
        return True
    return event_staff_status(user, event) != "closed"


def retreat_event_for_user(user: User, session) -> RetreatEvent | None:
    """`/retreat/` 진입 시 집회 — 세션 마지막 선택 우선, 없으면 default."""
    raw = session.get(SESSION_LAST_RETREAT_EVENT_ID)
    if raw is not None:
        try:
            event_id = int(raw)
        except (TypeError, ValueError):
            event_id = None
        if event_id:
            event = RetreatEvent.objects.filter(pk=event_id, is_active=True).first()
            if event and event_recallable_for_user(user, event):
                return event
    return default_retreat_event_for(user)


def url_for_retreat_tab(retreat_tab: str, event_id: int) -> str:
    """현재 상단 탭에 맞는 집회 URL."""
    tab = retreat_tab or "dashboard"
    if tab == "manage_groups":
        return reverse("retreat_group_manage_list", args=[event_id])
    if tab == "lodging":
        return reverse("retreat_lodging", args=[event_id])
    if tab == "lodging_roster":
        return reverse("retreat_lodging_roster", args=[event_id])
    if tab == "admin":
        return reverse("retreat_admin", args=[event_id])
    if tab == "council":
        return reverse("retreat_council", args=[event_id])
    if tab == "timetable":
        return reverse("retreat_timetable", args=[event_id])
    if tab == "pickup":
        return reverse("retreat_pickup", args=[event_id])
    if tab == "results":
        return reverse("retreat_results", args=[event_id])
    if tab == "rosters":
        return reverse("retreat_rosters", args=[event_id])
    if tab == "staff_apply":
        return reverse("retreat_staff_apply", args=[event_id])
    if tab == "staff_applications":
        return reverse("retreat_staff_applications", args=[event_id])
    return reverse("retreat_dashboard", args=[event_id])


def picker_target_url(user: User, event: RetreatEvent, *, retreat_tab: str) -> str:
    if has_retreat_operational_access(user, event):
        return url_for_retreat_tab(retreat_tab, event.id)
    return reverse("retreat_staff_apply", args=[event.id])


def picker_entries(user: User, *, retreat_tab: str) -> list[dict]:
    return [
        {
            "event": event,
            "url": picker_target_url(user, event, retreat_tab=retreat_tab),
        }
        for event in active_retreat_events()
    ]


def inject_picker_context(
    ctx: dict,
    user: User,
    event: RetreatEvent,
    *,
    retreat_tab: str,
) -> None:
    ctx["retreat_tab"] = retreat_tab
    ctx["picker_entries"] = picker_entries(user, retreat_tab=retreat_tab)
    ctx["available_events"] = [entry["event"] for entry in ctx["picker_entries"]]
