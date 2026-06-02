"""수련회 변경 이력 기록."""

from __future__ import annotations

from typing import Any

from django.db import models

from retreat.models import RetreatChangeLog, RetreatEvent


def serialize_model_fields(instance: models.Model, fields: list[str]) -> dict[str, Any]:
    """모델 인스턴스의 지정 필드를 JSON 직렬화 가능 dict 로 변환."""
    out: dict[str, Any] = {}
    for name in fields:
        val = getattr(instance, name, None)
        if isinstance(val, models.Model):
            out[name] = val.pk
        elif hasattr(val, "isoformat"):
            out[name] = val.isoformat()
        else:
            out[name] = val
    return out


def log_retreat_change(
    *,
    user,
    event: RetreatEvent | int,
    action: str,
    target_type: str,
    target_id: int,
    payload_before: dict | None = None,
    payload_after: dict | None = None,
) -> RetreatChangeLog:
    event_id = event.id if isinstance(event, RetreatEvent) else int(event)
    return RetreatChangeLog.objects.create(
        event_id=event_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload_before=payload_before,
        payload_after=payload_after,
        changed_by=user if getattr(user, "is_authenticated", False) else None,
    )
