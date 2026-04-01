import os

from celery import Celery

app = Celery('config')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()