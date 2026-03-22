"""조직(부서·팀·동아리·일하는 부서·직책)."""

from django.contrib import admin

from ..models import (
    Club,
    Division,
    FunctionalDepartment,
    MemberClub,
    MemberDivisionTeam,
    MemberFunctionalDeptRole,
    Role,
    Team,
    UserClub,
    UserDivisionTeam,
    UserFunctionalDeptRole,
)


class JccModelAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}


@admin.register(Division)
class DivisionAdmin(JccModelAdmin):
    list_display = ["name", "code", "parent", "sort_order"]
    list_filter = ["parent"]
    list_editable = ["sort_order"]
    search_fields = ["name", "code"]
    raw_id_fields = ["parent"]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("name", "code")}),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": ("parent", "sort_order"),
                "description": "상위 부서·정렬은 비워도 됩니다.",
            },
        ),
    )


@admin.register(Team)
class TeamAdmin(JccModelAdmin):
    list_display = ["name", "code", "division", "parent", "sort_order"]
    list_filter = ["division"]
    list_editable = ["sort_order"]
    search_fields = ["name", "code"]
    raw_id_fields = ["division", "parent"]
    autocomplete_fields = ["division"]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("division", "name", "code")}),
        ("선택", {"classes": ("jcc-optional",), "fields": ("parent", "sort_order")}),
    )


@admin.register(UserDivisionTeam)
class UserDivisionTeamAdmin(JccModelAdmin):
    list_display = ["user", "division", "team", "is_primary", "sort_order"]
    list_filter = ["division", "is_primary"]
    search_fields = ["user__username", "user__email"]
    autocomplete_fields = ["user", "division", "team"]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("user", "division")}),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": ("team", "is_primary", "sort_order"),
                "description": "팀 미지정 가능.",
            },
        ),
    )


@admin.register(UserClub)
class UserClubAdmin(JccModelAdmin):
    list_display = ["user", "club", "sort_order"]
    list_filter = ["club"]
    search_fields = ["user__username"]
    autocomplete_fields = ["user", "club"]


@admin.register(UserFunctionalDeptRole)
class UserFunctionalDeptRoleAdmin(JccModelAdmin):
    list_display = ["user", "functional_department", "role", "sort_order"]
    list_filter = ["functional_department", "role"]
    search_fields = ["user__username"]
    autocomplete_fields = ["user", "functional_department", "role"]


@admin.register(MemberDivisionTeam)
class MemberDivisionTeamAdmin(JccModelAdmin):
    list_display = ["member", "division", "team", "is_primary", "sort_order"]
    list_filter = ["division", "is_primary"]
    search_fields = ["member__name", "member__import_key"]
    autocomplete_fields = ["member", "division", "team"]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("member", "division")}),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": ("team", "is_primary", "sort_order"),
                "description": "팀 미지정 가능.",
            },
        ),
    )


@admin.register(Club)
class ClubAdmin(JccModelAdmin):
    list_display = ["name", "code", "division", "sort_order"]
    list_filter = ["division"]
    list_editable = ["sort_order"]
    search_fields = ["name", "code"]
    autocomplete_fields = ["division"]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("name", "code")}),
        ("선택", {"classes": ("jcc-optional",), "fields": ("division", "sort_order")}),
    )


@admin.register(MemberClub)
class MemberClubAdmin(admin.ModelAdmin):
    list_display = ["member", "club", "sort_order"]
    list_filter = ["club"]
    search_fields = ["member__name"]
    autocomplete_fields = ["member", "club"]


@admin.register(FunctionalDepartment)
class FunctionalDepartmentAdmin(JccModelAdmin):
    list_display = ["name", "code", "division", "sort_order"]
    list_filter = ["division"]
    list_editable = ["sort_order"]
    search_fields = ["name", "code"]
    autocomplete_fields = ["division"]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("name", "code")}),
        ("선택", {"classes": ("jcc-optional",), "fields": ("division", "sort_order")}),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "sort_order"]
    list_editable = ["sort_order"]
    search_fields = ["name", "code"]


@admin.register(MemberFunctionalDeptRole)
class MemberFunctionalDeptRoleAdmin(admin.ModelAdmin):
    list_display = ["member", "functional_department", "role", "sort_order"]
    list_filter = ["functional_department", "role"]
    search_fields = ["member__name"]
    autocomplete_fields = ["member", "functional_department", "role"]
