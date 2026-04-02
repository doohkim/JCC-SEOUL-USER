from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "attendance"
    label = "attendance"
    verbose_name = "출석"

    def ready(self) -> None:
        # Celery 기본 autodiscover는 워커 시작 시에만 동작해, Django(Admin·gunicorn)에서는
        # 태스크가 비어 django-celery-beat 검증이 실패한다. 앱 준비 후 강제 스캔한다.
        from config.celery import app

        app.autodiscover_tasks(force=True)
