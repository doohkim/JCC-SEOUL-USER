from django.apps import AppConfig


class NoticesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notices"
    verbose_name = "공지·일정"

    def ready(self):
        import notices.admin  # noqa: F401
