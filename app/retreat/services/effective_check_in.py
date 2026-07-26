"""예정 시각과 수동 예외를 합친 조원의 유효 입·퇴실 상태."""

from __future__ import annotations

from datetime import datetime

from django.db.models import Case, CharField, Q, Value, When
from django.utils import timezone

from retreat.models import RetreatAttendee


def status_from_expected_times(check_in_at, check_out_at, now) -> str:
    S = RetreatAttendee.CheckInStatus
    if check_in_at is None or check_in_at > now:
        return S.PENDING
    if check_out_at is not None and check_out_at <= now:
        return S.CHECKED_OUT
    return S.CHECKED_IN


def effective_status(attendee: RetreatAttendee, now: datetime | None = None) -> str:
    if attendee.check_in_status_manually_set:
        return attendee.check_in_status
    now = now or timezone.now()
    return status_from_expected_times(
        attendee.expected_check_in_at,
        attendee.expected_check_out_at,
        now,
    )


def effective_status_label(
    attendee: RetreatAttendee, now: datetime | None = None
) -> str:
    return dict(RetreatAttendee.CheckInStatus.choices)[effective_status(attendee, now)]


def effective_status_q(
    status: str,
    *,
    now: datetime | None = None,
    prefix: str = "",
) -> Q:
    """유효 상태로 queryset을 필터링할 Q를 반환한다."""
    now = now or timezone.now()
    S = RetreatAttendee.CheckInStatus
    normalized_prefix = prefix.rstrip("_")
    p = f"{normalized_prefix}__" if normalized_prefix else ""
    manual = Q(
        **{
            f"{p}check_in_status_manually_set": True,
            f"{p}check_in_status": status,
        }
    )
    automatic_base = Q(**{f"{p}check_in_status_manually_set": False})
    if status == S.PENDING:
        automatic = automatic_base & (
            Q(**{f"{p}expected_check_in_at__isnull": True})
            | Q(**{f"{p}expected_check_in_at__gt": now})
        )
    elif status == S.CHECKED_OUT:
        automatic = automatic_base & Q(
            **{
                f"{p}expected_check_in_at__isnull": False,
                f"{p}expected_check_in_at__lte": now,
                f"{p}expected_check_out_at__isnull": False,
                f"{p}expected_check_out_at__lte": now,
            }
        )
    elif status == S.CHECKED_IN:
        automatic = (
            automatic_base
            & Q(
                **{
                    f"{p}expected_check_in_at__isnull": False,
                    f"{p}expected_check_in_at__lte": now,
                }
            )
            & (
                Q(**{f"{p}expected_check_out_at__isnull": True})
                | Q(**{f"{p}expected_check_out_at__gt": now})
            )
        )
    else:
        raise ValueError(f"Unknown check-in status: {status}")
    return manual | automatic


def effective_status_expression(now: datetime | None = None):
    """현재 조원 queryset용 유효 상태 CASE 표현식."""
    now = now or timezone.now()
    S = RetreatAttendee.CheckInStatus
    return Case(
        When(check_in_status_manually_set=True, then="check_in_status"),
        When(
            Q(expected_check_in_at__isnull=True) | Q(expected_check_in_at__gt=now),
            then=Value(S.PENDING),
        ),
        When(
            expected_check_out_at__isnull=False,
            expected_check_out_at__lte=now,
            then=Value(S.CHECKED_OUT),
        ),
        default=Value(S.CHECKED_IN),
        output_field=CharField(),
    )
