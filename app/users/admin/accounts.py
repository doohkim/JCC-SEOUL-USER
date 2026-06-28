"""사용자(계정)·프로필·앱 조직 소속."""

from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.views.autocomplete import AutocompleteJsonView
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import path

from ..models import (
    User,
    UserClub,
    UserDivisionTeam,
    UserFunctionalDeptRole,
    UserProfile,
    UserProfileAvatar,
    RoleLevel,
)
from ..services.account_lifecycle import retire_user
from .audit import AuditLoggingModelAdminMixin
from .org_move import user_org_move_dashboard, user_org_move_detail


class UserAutocompleteJsonView(AutocompleteJsonView):
    """사용자 자동완성 드롭다운 라벨을 '핸드폰번호 · 실명'으로 표시(구별용)."""

    def serialize_result(self, obj, to_field_name):
        data = super().serialize_result(obj, to_field_name)
        phone = ""
        name = ""
        try:
            p = obj.profile
            name = (p.real_name or "").strip() or (p.display_name or "").strip()
            phone = (p.phone or "").strip()
        except UserProfile.DoesNotExist:
            pass
        parts = [part for part in (phone, name) if part]
        data["text"] = " · ".join(parts) if parts else (obj.username or str(obj.pk))
        return data


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
                    "real_name",
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
        "real_name",
        "phone_number",
        "signup_source",
        "role_level",
        "can_manage_accounts",
        "can_manage_attendance",
        "can_manage_parking",
        "onboarding_status",
        "is_staff",
        "is_active",
        "retired_at",
    ]
    list_filter = [
        "signup_source",
        "is_staff",
        "is_active",
        "retired_at",
        "role_level",
        "can_manage_accounts",
        "can_manage_attendance",
        "can_manage_parking",
        "profile__onboarding_status",
    ]
    search_fields = [
        "username",
        "email",
        "profile__display_name",
        "profile__real_name",
        "profile__phone",
    ]
    ordering = ["username"]
    inlines = [
        UserProfileInline,
        UserDivisionTeamInline,
        UserClubInline,
        UserFunctionalDeptRoleInline,
    ]
    actions = ["approve_onboarding", "reject_onboarding", "retire_accounts"]
    _org_permissions_fieldset = (
        "조직/권한",
        {
            "fields": (
                "signup_source",
                "role_level",
                "can_manage_accounts",
                "can_manage_attendance",
                "can_manage_parking",
            )
        },
    )
    fieldsets = (
        BaseUserAdmin.fieldsets[0],
        BaseUserAdmin.fieldsets[1],
        _org_permissions_fieldset,
        *BaseUserAdmin.fieldsets[2:],
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (_org_permissions_fieldset,)

    def delete_model(self, request, obj):
        try:
            retire_user(obj, changed_by=request.user)
            self.message_user(
                request,
                f"{obj} 계정을 탈퇴 처리했습니다(데이터 보존).",
                level=messages.SUCCESS,
            )
        except ValueError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_queryset(self, request, queryset):
        retired = 0
        skipped = 0
        for obj in queryset:
            try:
                retire_user(obj, changed_by=request.user)
                retired += 1
            except ValueError:
                skipped += 1
        if retired:
            self.message_user(
                request,
                f"{retired}명을 탈퇴 처리했습니다(데이터 보존).",
                level=messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f"{skipped}명은 탈퇴 처리할 수 없습니다(슈퍼유저 등).",
                level=messages.WARNING,
            )

    def autocomplete_view(self, request):
        return UserAutocompleteJsonView.as_view(admin_site=self.admin_site)(request)

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

    @admin.display(description="실명", ordering="profile__real_name")
    def real_name(self, obj):
        try:
            return obj.profile.real_name or obj.profile.display_name or "-"
        except UserProfile.DoesNotExist:
            return "-"

    @admin.display(description="휴대폰 번호", ordering="profile__phone")
    def phone_number(self, obj):
        try:
            return obj.profile.phone or "-"
        except UserProfile.DoesNotExist:
            return "-"

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
            was_already_approved = (
                profile.onboarding_status == UserProfile.OnboardingStatus.APPROVED
            )
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
            from users.services.onboarding_approval import apply_pastoral_account_setup

            apply_pastoral_account_setup(user_obj, profile)
            if not was_already_approved:
                from retreat.services.onboarding import sync_retreat_attendee_from_onboarding_profile

                sync_retreat_attendee_from_onboarding_profile(
                    user=user_obj,
                    profile=profile,
                    changed_by=request.user,
                )
            elif profile.requested_retreat_participation and profile.requested_retreat_group_id:
                from retreat.services.onboarding import (
                    retreat_attendee_exists_for_profile,
                    sync_retreat_attendee_from_onboarding_profile,
                )

                if not retreat_attendee_exists_for_profile(profile):
                    sync_retreat_attendee_from_onboarding_profile(
                        user=user_obj,
                        profile=profile,
                        changed_by=request.user,
                    )
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

    @admin.action(description="선택 사용자 탈퇴 처리(데이터 보존)")
    def retire_accounts(self, request, queryset):
        retired = 0
        skipped = 0
        for user_obj in queryset:
            try:
                retire_user(user_obj, changed_by=request.user)
                retired += 1
            except ValueError:
                skipped += 1
        if retired:
            self.message_user(
                request,
                f"{retired}명을 탈퇴 처리했습니다(데이터 보존).",
                level=messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f"{skipped}명은 탈퇴 처리할 수 없습니다.",
                level=messages.WARNING,
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


@admin.register(UserProfileAvatar)
class UserProfileAvatarAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}

    list_display = [
        "username_snapshot",
        "user_id_snapshot",
        "user_profile",
        "content_hash",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = [
        "content_hash",
        "username_snapshot",
        "user_profile__user__username",
        "source_url",
    ]
    readonly_fields = [
        "image",
        "source_url",
        "content_hash",
        "created_at",
        "user_profile",
        "user_id_snapshot",
        "username_snapshot",
    ]
