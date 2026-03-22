from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "users"

    def ready(self):
        _install_admin_users_grouping()

        from django.db.models.signals import post_save

        from users.models import Member, MemberProfile

        def ensure_member_profile(sender, instance: Member, created, **kwargs):
            if created:
                MemberProfile.objects.get_or_create(member=instance)

        post_save.connect(ensure_member_profile, sender=Member, weak=False)


def _install_admin_users_grouping() -> None:
    """관리자 메인 화면에서 ``users`` 앱만 모델을 성격별 섹션·태그로 묶음."""
    from django.contrib.admin.sites import AdminSite

    if getattr(AdminSite, "_jcc_users_grouping_installed", False):
        return

    _original = AdminSite.get_app_list

    def get_app_list(self, request, app_label=None):
        app_list = _original(self, request, app_label)
        for app in app_list:
            if app.get("app_label") != "users":
                continue
            from users.admin.grouping import group_users_models_for_template

            app["jcc_model_groups"] = group_users_models_for_template(app["models"])
        return app_list

    AdminSite.get_app_list = get_app_list  # type: ignore[method-assign]
    AdminSite._jcc_users_grouping_installed = True
