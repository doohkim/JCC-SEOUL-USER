"""조원 연락처 — 집회 단위 중복 검사 (API 검증용, DB 제약 없음)."""

from __future__ import annotations

from retreat.models import RetreatAttendee
from users.validators import normalize_korea_mobile_phone


def phone_match_key(raw: str) -> str:
    """비교용 정규화 키. 없거나 비정상이면 빈 문자열."""
    normalized = normalize_korea_mobile_phone((raw or "").strip())
    return normalized or ""


def find_event_phone_duplicate(
    *,
    event_id: int,
    phone: str,
    exclude_attendee_id: int | None = None,
) -> RetreatAttendee | None:
    """같은 집회에 동일 번호(비어 있지 않음·비탈퇴) 조원이 있으면 그 행.

    빈 번호는 검사하지 않는다. 탈퇴(``account_retired_at``) 행은 제외.
    """
    key = phone_match_key(phone)
    if not key:
        return None

    qs = (
        RetreatAttendee.objects.filter(
            group__event_id=event_id,
            account_retired_at__isnull=True,
        )
        .exclude(phone="")
        .select_related("group")
        .order_by("id")
    )
    if exclude_attendee_id is not None:
        qs = qs.exclude(pk=exclude_attendee_id)

    for row in qs.iterator(chunk_size=200):
        if phone_match_key(row.phone) == key:
            return row
    return None
