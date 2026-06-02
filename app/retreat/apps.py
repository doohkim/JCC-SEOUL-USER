from django.apps import AppConfig


class RetreatConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "retreat"
    label = "retreat"
    verbose_name = "수련회"

    def ready(self):
        import retreat.admin  # noqa: F401
        import retreat.signals  # noqa: F401
