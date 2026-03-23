"""교적 조직 소속 (Member ↔ Division/Team/Club …)."""

from django.contrib import admin

from registry.admin.pastoral_mixin import PastoralRegistryModelAdminMixin
from registry.models import MemberClub, MemberDivisionTeam, MemberFunctionalDeptRole


class JccModelAdmin(PastoralRegistryModelAdminMixin, admin.ModelAdmin):
    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}


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


@admin.register(MemberClub)
class MemberClubAdmin(PastoralRegistryModelAdminMixin, admin.ModelAdmin):
    list_display = ["member", "club", "sort_order"]
    list_filter = ["club"]
    search_fields = ["member__name"]
    autocomplete_fields = ["member", "club"]


@admin.register(MemberFunctionalDeptRole)
class MemberFunctionalDeptRoleAdmin(PastoralRegistryModelAdminMixin, admin.ModelAdmin):
    list_display = ["member", "functional_department", "role", "sort_order"]
    list_filter = ["functional_department", "role"]
    search_fields = ["member__name"]
    autocomplete_fields = ["member", "functional_department", "role"]
