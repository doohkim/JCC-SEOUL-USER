__all__ = ("INSTALLED_APPS",)

ADMIN_APPS = []

THIRD_PARTY_APPS = [
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
    # "django_crontab",
    # "django_extensions",
    "django_filters",
    "phonenumber_field",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
]

LOCAL_APPS = [
    "social_django",
    "users",
    "registry",
    "attendance",
    "counseling",
    "utils",
]

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

INSTALLED_APPS = ADMIN_APPS + THIRD_PARTY_APPS + LOCAL_APPS + DJANGO_APPS
