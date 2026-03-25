"""사용자(계정)·프로필·앱 조직 소속."""

from django.contrib import admin
from django.contrib import messages
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
                    "onboarding_status",
                    "requested_division",
                    "requested_team",
                    "onboarding_note",
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

    list_display = [
        "username",
        "email",
        "role_level",
        "onboarding_status",
        "is_staff",
        "is_active",
    ]
    list_filter = ["is_staff", "is_active", "role_level", "profile__onboarding_status"]
    search_fields = ["username", "email", "profile__display_name", "profile__phone"]
    ordering = ["username"]
    inlines = [
        UserProfileInline,
        UserDivisionTeamInline,
        UserClubInline,
        UserFunctionalDeptRoleInline,
    ]
    actions = ["approve_onboarding", "reject_onboarding"]
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

    @admin.display(description="온보딩 상태")
    def onboarding_status(self, obj):
        try:
            return obj.profile.get_onboarding_status_display()
        except UserProfile.DoesNotExist:
            return "프로필 없음"

    @admin.action(description="선택 사용자 온보딩 승인")
    def approve_onboarding(self, request, queryset):
        approved_count = 0
        skipped_count = 0
        for user_obj in queryset:
            profile, _ = UserProfile.objects.get_or_create(user=user_obj)
            if not profile.requested_division_id:
                skipped_count += 1
                continue
            req_team = profile.requested_team
            if req_team and req_team.division_id != profile.requested_division_id:
                req_team = None
            membership, created = UserDivisionTeam.objects.get_or_create(
                user=user_obj,
                division=profile.requested_division,
                defaults={"team": req_team, "is_primary": True, "sort_order": 0},
            )
            if not created:
                tid = req_team.id if req_team else None
                if membership.team_id != tid:
                    membership.team = req_team
                    membership.save(update_fields=["team"])
                if not membership.is_primary:
                    membership.is_primary = True
                    membership.save(update_fields=["is_primary"])
            profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
            profile.onboarding_note = ""
            profile.save(update_fields=["onboarding_status", "onboarding_note", "updated_at"])
            approved_count += 1
        if approved_count:
            self.message_user(
                request,
                f"{approved_count}명의 온보딩을 승인했습니다.",
                level=messages.SUCCESS,
            )
        if skipped_count:
            self.message_user(
                request,
                f"{skipped_count}명은 신청 부서가 없어 건너뛰었습니다.",
                level=messages.WARNING,
            )

    @admin.action(description="선택 사용자 온보딩 반려")
    def reject_onboarding(self, request, queryset):
        updated = 0
        for user_obj in queryset:
            profile, _ = UserProfile.objects.get_or_create(user=user_obj)
            profile.onboarding_status = UserProfile.OnboardingStatus.REJECTED
            if not profile.onboarding_note:
                profile.onboarding_note = "소속 정보 확인 후 다시 신청해 주세요."
            profile.save(update_fields=["onboarding_status", "onboarding_note", "updated_at"])
            updated += 1
        self.message_user(
            request,
            f"{updated}명을 반려 상태로 변경했습니다.",
            level=messages.INFO,
        )


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
