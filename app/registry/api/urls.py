from django.urls import path

from registry.api.views import (
    MemberMembershipListView,
    OrgChangeTeamView,
    OrgTransferDivisionView,
)

urlpatterns = [
    path("change-team/", OrgChangeTeamView.as_view(), name="api_org_change_team"),
    path(
        "transfer-division/",
        OrgTransferDivisionView.as_view(),
        name="api_org_transfer_division",
    ),
    path(
        "memberships/",
        MemberMembershipListView.as_view(),
        name="api_org_memberships_list",
    ),
]
