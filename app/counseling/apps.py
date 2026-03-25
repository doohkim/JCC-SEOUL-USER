from django.apps import AppConfig


class CounselingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "counseling"
    label = "counseling"
    verbose_name = "상담"

    def ready(self):
        import counseling.admin  # noqa: F401
