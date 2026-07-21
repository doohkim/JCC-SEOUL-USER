"""수련회 변경 이력 목록 필터·페이지 쿼리."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import CharField, Q, QuerySet
from django.db.models.functions import Cast
from django.utils import timezone
from django.utils.dateparse import parse_date

from retreat.models import RetreatChangeLog, RetreatEvent

User = get_user_model()

CHANGELOG_PAGE_SIZE = 20
CHANGELOG_API_MAX_PAGE_SIZE = 100


def parse_changelog_filters(params) -> dict[str, Any]:
    """GET/query params → 정규화된 필터 dict."""
    q = str(params.get("q") or "").strip()
    date_from = _parse_date_param(params.get("date_from"))
    date_to = _parse_date_param(params.get("date_to"))
    actor_raw = str(params.get("actor") or "").strip()
    actor_id = None
    if actor_raw.isdigit():
        actor_id = int(actor_raw)
    target_type = str(params.get("target_type") or "").strip()
    if target_type and target_type not in RetreatChangeLog.TargetType.values:
        target_type = ""
    action = str(params.get("action") or "").strip()
    if action and action not in RetreatChangeLog.Action.values:
        action = ""
    return {
        "q": q,
        "date_from": date_from,
        "date_to": date_to,
        "actor_id": actor_id,
        "target_type": target_type,
        "action": action,
    }


def changelog_queryset_for_event(
    event: RetreatEvent,
    *,
    q: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    actor_id: int | None = None,
    target_type: str = "",
    action: str = "",
) -> QuerySet[RetreatChangeLog]:
    qs = RetreatChangeLog.objects.filter(event=event).select_related(
        "changed_by", "changed_by__profile"
    )
    if date_from is not None:
        start = timezone.make_aware(datetime.combine(date_from, time.min))
        qs = qs.filter(changed_at__gte=start)
    if date_to is not None:
        end = timezone.make_aware(datetime.combine(date_to, time.max))
        qs = qs.filter(changed_at__lte=end)
    if actor_id is not None:
        qs = qs.filter(changed_by_id=actor_id)
    if target_type:
        qs = qs.filter(target_type=target_type)
    if action:
        qs = qs.filter(action=action)
    q = (q or "").strip()
    if q:
        qs = qs.annotate(
            payload_before_text=Cast("payload_before", CharField()),
            payload_after_text=Cast("payload_after", CharField()),
        ).filter(
            Q(changed_by__username__icontains=q)
            | Q(changed_by__profile__real_name__icontains=q)
            | Q(changed_by__profile__display_name__icontains=q)
            | Q(payload_before_text__icontains=q)
            | Q(payload_after_text__icontains=q)
        )
    return qs.order_by("-changed_at", "-id")


def changelog_actors_for_event(event: RetreatEvent) -> list:
    """해당 집회 로그에 등장한 작업자 목록 (표시명 정렬)."""
    users = list(
        User.objects.filter(retreat_change_logs__event=event)
        .select_related("profile")
        .distinct()
    )

    def label(u) -> str:
        profile = getattr(u, "profile", None)
        name = ""
        if profile is not None:
            name = (profile.real_name or profile.display_name or "").strip()
        return name or u.get_username()

    users.sort(key=lambda u: (label(u), u.get_username(), u.pk))
    return [{"id": u.pk, "label": label(u)} for u in users]


def parse_page(params, *, default: int = 1) -> int:
    raw = str(params.get("page") or default).strip()
    try:
        page = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, page)


def parse_page_size(
    params,
    *,
    default: int = CHANGELOG_PAGE_SIZE,
    maximum: int = CHANGELOG_API_MAX_PAGE_SIZE,
) -> int:
    raw = str(params.get("page_size") or params.get("limit") or default).strip()
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(size, maximum))


def _parse_date_param(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    return parse_date(text)
