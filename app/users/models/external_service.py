"""외부 서버(연동 시스템)용 API 클라이언트 — 서비스 키로 식별."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def _pepper_bytes() -> bytes:
    p = getattr(settings, "INTEGRATION_KEY_PEPPER", None) or settings.SECRET_KEY
    return str(p).encode("utf-8")


def hash_integration_key(raw_key: str) -> str:
    """저장용 SHA-256 해시 (페퍼 + 키)."""
    d = hashlib.sha256()
    d.update(_pepper_bytes())
    d.update(b"\x00")
    d.update(raw_key.encode("utf-8"))
    return d.hexdigest()


def generate_integration_key_pair() -> tuple[str, str, str]:
    """
    (평문 키, key_prefix, key_hash) 생성.
    prefix는 조회용으로 앞 16자 고정.
    """
    raw = secrets.token_urlsafe(48)
    prefix = raw[:16]
    return raw, prefix, hash_integration_key(raw)


class ExternalServiceClient(models.Model):
    """
    연동 서버 1건당 1행. 발급된 평문 키는 최초 1회만 표시(Admin 메시지).
    """

    name = models.SlugField("연동 식별자", max_length=64, unique=True, db_index=True)
    label = models.CharField("표시 이름", max_length=128, blank=True, default="")
    key_prefix = models.CharField(max_length=16, db_index=True, blank=True, default="")
    key_hash = models.CharField(max_length=64, editable=False, blank=True, default="")
    is_active = models.BooleanField("사용", default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField("비고", blank=True, default="")

    class Meta:
        db_table = "users_externalserviceclient"
        verbose_name = "연동 API 클라이언트"
        verbose_name_plural = "연동 API 클라이언트"

    def __str__(self) -> str:
        return f"{self.label or self.name} ({self.name})"

    def check_key(self, raw_key: str) -> bool:
        if not raw_key or not self.key_hash:
            return False
        expect = hash_integration_key(raw_key)
        return hmac.compare_digest(self.key_hash, expect)

    def touch_last_used(self) -> None:
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at", "updated_at"])
