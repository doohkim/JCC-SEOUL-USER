"""계정 탈퇴로 숨김 처리된 조원·픽업 조회 필터."""

from __future__ import annotations

from django.db.models import Q, QuerySet
from django.http import Http404
from django.utils import timezone

from retreat.models import RetreatAttendee, RetreatPickup
from retreat.services.pickup_attendee import pickups_for_attendee

ACCOUNT_RETIRED_DISPLAY = "탈퇴 계정"


def can_view_retired_account_data(user) -> bool:
    return bool(getattr(user, "is_superuser", False))


def is_retired_account_row(obj) -> bool:
    retired_at = getattr(obj, "account_retired_at", None)
    return retired_at is not None


def exclude_retired_attendees_q(*, prefix: str = "") -> Q:
    return Q(**{f"{prefix}account_retired_at__isnull": True})


def exclude_retired_pickups_q(*, prefix: str = "") -> Q:
    return Q(**{f"{prefix}account_retired_at__isnull": True})


def visible_attendees_for(user, qs: QuerySet) -> QuerySet:
    if can_view_retired_account_data(user):
        return qs
    return qs.filter(account_retired_at__isnull=True)


def visible_pickups_for(user, qs: QuerySet) -> QuerySet:
    if can_view_retired_account_data(user):
        return qs
    return qs.filter(account_retired_at__isnull=True)


def assert_attendee_visible_to(user, attendee: RetreatAttendee) -> None:
    if can_view_retired_account_data(user):
        return
    if is_retired_account_row(attendee):
        raise Http404


def assert_pickup_visible_to(user, pickup: RetreatPickup) -> None:
    if can_view_retired_account_data(user):
        return
    if is_retired_account_row(pickup):
        raise Http404


def mark_attendees_retired_for_user(user, *, when=None) -> int:
    """탈퇴 계정에 연결된 조원·픽업을 숨김 마킹한다."""
    retired_at = when or timezone.now()
    marked = 0
    attendees = list(RetreatAttendee.objects.filter(user=user))
    for attendee in attendees:
        if attendee.account_retired_at is None:
            attendee.account_retired_at = retired_at
            attendee.save(update_fields=["account_retired_at", "updated_at"])
            marked += 1
        for pickup in pickups_for_attendee(attendee):
            if pickup.account_retired_at is None:
                pickup.account_retired_at = retired_at
                pickup.save(update_fields=["account_retired_at", "updated_at"])
    return marked
