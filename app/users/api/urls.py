from django.urls import path

from users.api.views import (
    MemberMembershipListView,
    OrgChangeTeamView,
    OrgTransferDivisionView,
)

urlpatterns = [
    path("org/change-team/", OrgChangeTeamView.as_view(), name="api_org_change_team"),
    path(
        "org/transfer-division/",
        OrgTransferDivisionView.as_view(),
        name="api_org_transfer_division",
    ),
    path(
        "org/memberships/",
        MemberMembershipListView.as_view(),
        name="api_org_memberships_list",
    ),
]
