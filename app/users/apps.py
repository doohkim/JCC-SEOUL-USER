from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "users"

    def ready(self):
        from config.admin_app_list import ensure_admin_app_list_grouping

        ensure_admin_app_list_grouping()
        import users.openapi_extensions  # noqa: F401 — drf-spectacular 확장 등록
