"""Django 패키지 로드 시 Celery 앱을 함께 올려 태스크가 등록되게 한다 (Admin·beat 검증용)."""

from .celery import app as celery_app

__all__ = ("celery_app",)
