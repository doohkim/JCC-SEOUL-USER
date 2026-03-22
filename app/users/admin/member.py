"""멤버(교적) — 교적 프로필·조직·가족·심방."""

from django.contrib import admin
from django.urls import path

from ..models import (
    Member,
    MemberClub,
    MemberDivisionTeam,
    MemberFamilyMember,
    MemberFunctionalDeptRole,
    MemberProfile,
    MemberVisitLog,
)
from .audit import AuditLoggingModelAdminMixin
from .org_move import member_org_move_dashboard, member_org_move_detail


class MemberProfileInline(admin.StackedInline):
    model = MemberProfile
    can_delete = False
    max_num = 1
    extra = 0
    fk_name = "member"
    fieldsets = (
        (
            "교적 카드",
            {
                "fields": (
                    "birth_date",
                    "phone",
                    "address",
                    "church_position_display",
                    "workplace_display",
                    "photo",
                    "family_photo",
                ),
            },
        ),
        (
            "목회 메모",
            {"classes": ("collapse",), "fields": ("staff_notes",)},
        ),
    )


class MemberDivisionTeamInline(admin.TabularInline):
    model = MemberDivisionTeam
    extra = 0
    autocomplete_fields = ["division", "team"]


class MemberClubInline(admin.TabularInline):
    model = MemberClub
    extra = 0
    autocomplete_fields = ["club"]


class MemberFunctionalDeptRoleInline(admin.TabularInline):
    model = MemberFunctionalDeptRole
    extra = 0
    autocomplete_fields = ["functional_department", "role"]


class MemberFamilyMemberInline(admin.TabularInline):
    model = MemberFamilyMember
    extra = 0
    fk_name = "member"
    autocomplete_fields = ["division"]
    ordering = ["sort_order", "id"]


class MemberVisitLogInline(admin.TabularInline):
    model = MemberVisitLog
    extra = 0
    fk_name = "member"
    autocomplete_fields = ["recorded_by"]
    readonly_fields = ["created_at"]
    ordering = ["-visit_date", "-created_at"]


@admin.register(MemberFamilyMember)
class MemberFamilyMemberAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}

    list_display = [
        "member",
        "name",
        "relationship",
        "affiliation_text",
        "church_position",
        "sort_order",
    ]
    list_filter = ["relationship"]
    search_fields = ["name", "affiliation_text", "member__name"]
    autocomplete_fields = ["member", "division"]


@admin.register(MemberVisitLog)
class MemberVisitLogAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}

    list_display = ["member", "visit_date", "contact_method", "recorded_by", "created_at"]
    list_filter = ["contact_method", "visit_date"]
    search_fields = ["content", "member__name"]
    autocomplete_fields = ["member", "recorded_by"]
    date_hierarchy = "visit_date"
    fieldsets = (
        (
            "필수",
            {
                "classes": ("jcc-required",),
                "fields": ("member", "visit_date", "contact_method", "content"),
                "description": "심방·통화 내용을 기록합니다.",
            },
        ),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": ("recorded_by",),
                "description": "비워도 됩니다.",
            },
        ),
        (
            "시스템",
            {"classes": ("collapse", "jcc-optional"), "fields": ("created_at",)},
        ),
    )
    readonly_fields = ["created_at"]


@admin.register(Member)
class MemberAdmin(AuditLoggingModelAdminMixin, admin.ModelAdmin):
    """교적 카드: 상세 프로필, 부서·팀, 동아리, 일하는 부서, 가족, 심방."""

    change_form_template = "admin/users/member/change_form.html"

    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}

    list_display = ["name", "name_alias", "linked_user", "is_active", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "name_alias", "import_key", "pastoral_profile__phone"]
    autocomplete_fields = ["linked_user"]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
    inlines = [
        MemberProfileInline,
        MemberDivisionTeamInline,
        MemberClubInline,
        MemberFunctionalDeptRoleInline,
        MemberFamilyMemberInline,
        MemberVisitLogInline,
    ]
    fieldsets = (
        (
            "필수",
            {"classes": ("jcc-required",), "fields": ("name",)},
        ),
        (
            "선택",
            {
                "classes": ("wide", "jcc-optional"),
                "fields": (
                    "name_alias",
                    "import_key",
                    "linked_user",
                    "is_active",
                ),
            },
        ),
        (
            "시스템",
            {
                "classes": ("collapse", "jcc-optional"),
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
            },
        ),
    )

    def get_urls(self):
        opts = self.model._meta
        info = opts.model_name
        extra = [
            path(
                "org-move/",
                self.admin_site.admin_view(member_org_move_dashboard),
                name=f"{opts.app_label}_{info}_org_move_dashboard",
            ),
            path(
                "<path:object_id>/org-move/",
                self.admin_site.admin_view(member_org_move_detail),
                name=f"{opts.app_label}_{info}_org_move",
            ),
        ]
        return extra + super().get_urls()
