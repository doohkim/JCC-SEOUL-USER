import os

from . import _secrets as secrets

IS_DOCKER = bool(os.environ.get("DOCKER"))
RABBITMQ_HOST = "rabbitmq" if IS_DOCKER else "127.0.0.1"
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "jccseoul" if IS_DOCKER else "guest")
RABBITMQ_PASSWORD = os.environ.get(
    "RABBITMQ_PASSWORD",
    "jccseoul1!" if IS_DOCKER else "",
)

CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BROKER_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:5672//"
CELERY_RESULT_EXTENDED = True
CELERY_TASK_TRACK_STARTED = True  # 실행 중인 Task도 저장

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
