"""사용자(계정)·프로필·앱 조직 소속."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import path

from ..models import (
    User,
    UserClub,
    UserDivisionTeam,
    UserFunctionalDeptRole,
    UserProfile,
    RoleLevel,
)
from .audit import AuditLoggingModelAdminMixin
from .org_move import user_org_move_dashboard, user_org_move_detail


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    max_num = 1
    extra = 0
    fk_name = "user"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "display_name",
                    "phone",
                    "phone_verified",
                    "phone_verified_at",
                    "avatar",
                    "bio",
                ),
            },
        ),
        (
            "휴대폰 인증(OTP)",
            {
                "classes": ("collapse",),
                "fields": (
                    "phone_otp_hash",
                    "phone_otp_expires_at",
                    "phone_otp_attempts",
                ),
            },
        ),
    )
    readonly_fields = ["phone_verified_at"]


class UserDivisionTeamInline(admin.TabularInline):
    model = UserDivisionTeam
    extra = 0
    autocomplete_fields = ["division", "team"]


class UserClubInline(admin.TabularInline):
    model = UserClub
    extra = 0
    autocomplete_fields = ["club"]


class UserFunctionalDeptRoleInline(admin.TabularInline):
    model = UserFunctionalDeptRole
    extra = 0
    autocomplete_fields = ["functional_department", "role"]


@admin.register(User)
class UserAdmin(AuditLoggingModelAdminMixin, BaseUserAdmin):
    change_form_template = "admin/users/user/change_form.html"

    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}

    list_display = ["username", "email", "role_level", "is_staff", "is_active"]
    list_filter = ["is_staff", "is_active", "role_level"]
    search_fields = ["username", "email", "profile__display_name", "profile__phone"]
    ordering = ["username"]
    inlines = [
        UserProfileInline,
        UserDivisionTeamInline,
        UserClubInline,
        UserFunctionalDeptRoleInline,
    ]
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "조직/권한",
            {"fields": ("role_level",)},
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("조직/권한", {"fields": ("role_level",)}),)

    def get_urls(self):
        opts = self.model._meta
        info = opts.model_name
        extra = [
            path(
                "org-move/",
                self.admin_site.admin_view(user_org_move_dashboard),
                name=f"{opts.app_label}_{info}_org_move_dashboard",
            ),
            path(
                "<path:object_id>/org-move/",
                self.admin_site.admin_view(user_org_move_detail),
                name=f"{opts.app_label}_{info}_org_move",
            ),
        ]
        return extra + super().get_urls()


@admin.register(RoleLevel)
class RoleLevelAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}

    list_display = ["name", "code", "level", "sort_order"]
    list_editable = ["level", "sort_order"]
    search_fields = ["name", "code"]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("name", "code", "level")}),
        ("선택", {"classes": ("jcc-optional",), "fields": ("sort_order",)}),
    )
