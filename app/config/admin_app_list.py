"""Admin 앱 목록에 교적·출석·users 모델 그룹(태그) 적용."""

from __future__ import annotations


def ensure_admin_app_list_grouping() -> None:
    from django.contrib.admin.sites import AdminSite

    if getattr(AdminSite, "_jcc_app_list_grouping", False):
        return

    from attendance.admin.grouping import group_attendance_models_for_template
    from registry.admin.grouping import group_registry_models_for_template
    from users.admin.grouping import group_users_models_for_template

    _original = AdminSite.get_app_list

    def get_app_list(self, request, app_label=None):
        app_list = _original(self, request, app_label)
        for app in app_list:
            label = app.get("app_label")
            if label == "users":
                app["jcc_model_groups"] = group_users_models_for_template(app["models"])
            elif label == "registry":
                app["jcc_model_groups"] = group_registry_models_for_template(app["models"])
            elif label == "attendance":
                app["jcc_model_groups"] = group_attendance_models_for_template(app["models"])
        return app_list

    AdminSite.get_app_list = get_app_list  # type: ignore[method-assign]
    AdminSite._jcc_app_list_grouping = True
