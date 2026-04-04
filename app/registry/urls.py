"""registry 앱 URL (교적·조직 DRF)."""

from django.urls import path

from registry.apis.member_crud import (
    MemberDetailUpdateView,
    MemberFamilyDetailView,
    MemberFamilyListCreateView,
    MemberListCreateView,
    MemberLinkUserChoicesView,
    MemberLinkUserSetView,
    MemberRegistryTeamsAccordionView,
    MemberRoleOptionsView,
    MemberVisitLogDetailView,
    MemberVisitLogListCreateView,
)
from registry.apis.views import (
    MemberMembershipListView,
    OrgChangeTeamView,
    OrgTransferDivisionView,
)
from registry.views import (
    RegistryMemberCreatePageView,
    RegistryMemberDetailPageView,
    RegistryMemberEditPageView,
    RegistryMemberFamilyPageView,
    RegistryMemberListPageView,
)

urlpatterns = [
    # 교적부 페이지
    path("members/", RegistryMemberListPageView.as_view(), name="registry_member_list"),
    path(
        "members/create/",
        RegistryMemberCreatePageView.as_view(),
        name="registry_member_create",
    ),
    path(
        "members/<int:member_id>/",
        RegistryMemberDetailPageView.as_view(),
        name="registry_member_detail",
    ),
    path(
        "members/<int:member_id>/edit/",
        RegistryMemberEditPageView.as_view(),
        name="registry_member_edit",
    ),
    path(
        "members/<int:member_id>/family/",
        RegistryMemberFamilyPageView.as_view(),
        name="registry_member_family",
    ),

    path(
        "api/v1/org/change-team/",
        OrgChangeTeamView.as_view(),
        name="api_org_change_team",
    ),
    path(
        "api/v1/org/transfer-division/",
        OrgTransferDivisionView.as_view(),
        name="api_org_transfer_division",
    ),
    path(
        "api/v1/org/memberships/",
        MemberMembershipListView.as_view(),
        name="api_org_memberships_list",
    ),

    # 교적부 CRUD API
    path("api/v1/member/", MemberListCreateView.as_view(), name="api_member_list_create"),
    path(
        "api/v1/member/<int:member_id>/",
        MemberDetailUpdateView.as_view(),
        name="api_member_detail_update",
    ),
    path(
        "api/v1/member/<int:member_id>/link-user/choices/",
        MemberLinkUserChoicesView.as_view(),
        name="api_member_link_user_choices",
    ),
    path(
        "api/v1/member/<int:member_id>/link-user/",
        MemberLinkUserSetView.as_view(),
        name="api_member_link_user_set",
    ),
    path(
        "api/v1/member/<int:member_id>/family/",
        MemberFamilyListCreateView.as_view(),
        name="api_member_family_list_create",
    ),
    path(
        "api/v1/family/<int:family_id>/",
        MemberFamilyDetailView.as_view(),
        name="api_member_family_detail",
    ),
    path(
        "api/v1/member/<int:member_id>/visits/",
        MemberVisitLogListCreateView.as_view(),
        name="api_member_visit_list_create",
    ),
    path(
        "api/v1/visits/<int:visit_id>/",
        MemberVisitLogDetailView.as_view(),
        name="api_member_visit_detail",
    ),

    # 교적부 목록(팀별 아코디언) - 팀/부서/팀원 구조 응답
    path(
        "api/v1/member/teams/accordion/",
        MemberRegistryTeamsAccordionView.as_view(),
        name="api_member_teams_accordion",
    ),
    path("api/v1/member/roles/", MemberRoleOptionsView.as_view(), name="api_member_roles_list"),
]
