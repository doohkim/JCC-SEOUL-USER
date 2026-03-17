from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Club,
    Division,
    FunctionalDepartment,
    Role,
    RoleLevel,
    Team,
    User,
    UserClub,
    UserDivisionTeam,
    UserFunctionalDeptRole,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "name_ko", "email", "role_level", "is_staff", "is_active"]
    list_filter = ["is_staff", "is_active", "role_level"]
    search_fields = ["username", "name_ko", "email"]
    ordering = ["name_ko"]
    inlines = []
    fieldsets = BaseUserAdmin.fieldsets + (
        ("조직/권한", {"fields": ("name_ko", "role_level")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("조직/권한", {"fields": ("name_ko", "role_level")}),
    )


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


UserAdmin.inlines = [UserDivisionTeamInline, UserClubInline, UserFunctionalDeptRoleInline]


@admin.register(RoleLevel)
class RoleLevelAdmin(admin.ModelAdmin):
    list_display = ["name_ko", "code", "level", "sort_order"]
    list_editable = ["level", "sort_order"]
    search_fields = ["name_ko", "code"]


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ["name_ko", "code", "parent", "sort_order"]
    list_filter = ["parent"]
    list_editable = ["sort_order"]
    search_fields = ["name_ko", "code"]
    raw_id_fields = ["parent"]


class TeamInline(admin.TabularInline):
    model = Team
    extra = 0
    raw_id_fields = ["parent"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name_ko", "code", "division", "parent", "sort_order"]
    list_filter = ["division"]
    list_editable = ["sort_order"]
    search_fields = ["name_ko", "code"]
    raw_id_fields = ["division", "parent"]
    autocomplete_fields = ["division"]


@admin.register(UserDivisionTeam)
class UserDivisionTeamAdmin(admin.ModelAdmin):
    list_display = ["user", "division", "team", "is_primary", "sort_order"]
    list_filter = ["division", "is_primary"]
    search_fields = ["user__name_ko", "user__username"]
    autocomplete_fields = ["user", "division", "team"]


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ["name_ko", "code", "division", "sort_order"]
    list_filter = ["division"]
    list_editable = ["sort_order"]
    search_fields = ["name_ko", "code"]
    autocomplete_fields = ["division"]


@admin.register(UserClub)
class UserClubAdmin(admin.ModelAdmin):
    list_display = ["user", "club", "sort_order"]
    list_filter = ["club"]
    search_fields = ["user__name_ko"]
    autocomplete_fields = ["user", "club"]


@admin.register(FunctionalDepartment)
class FunctionalDepartmentAdmin(admin.ModelAdmin):
    list_display = ["name_ko", "code", "division", "sort_order"]
    list_filter = ["division"]
    list_editable = ["sort_order"]
    search_fields = ["name_ko", "code"]
    autocomplete_fields = ["division"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name_ko", "code", "sort_order"]
    list_editable = ["sort_order"]
    search_fields = ["name_ko", "code"]


@admin.register(UserFunctionalDeptRole)
class UserFunctionalDeptRoleAdmin(admin.ModelAdmin):
    list_display = ["user", "functional_department", "role", "sort_order"]
    list_filter = ["functional_department", "role"]
    search_fields = ["user__name_ko"]
    autocomplete_fields = ["user", "functional_department", "role"]
