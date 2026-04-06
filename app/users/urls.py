"""users 앱 URL (계정·인증 전용 라우트)."""

from django.urls import path
from django.views.generic import RedirectView

from users.apis.integration import (
    IntegrationIssueTokenDebugView,
    IntegrationPermissionCheckView,
    IntegrationPingView,
    IntegrationUserDetailView,
    IntegrationVerifyTokenView,
)
from users.views import (
    AssignableRoleOptionsApiView,
    DivisionAccountRoleManageView,
    KakaoAuthEntryView,
    OnboardingApprovalListView,
    UserLogoutView,
    UserOnboardingView,
)

urlpatterns = [
    path("login/", KakaoAuthEntryView.as_view(), name="user_login"),
    path("logout/", UserLogoutView.as_view(), name="user_logout"),
    path("signup/", RedirectView.as_view(pattern_name="user_login", permanent=False)),
    path("onboarding/", UserOnboardingView.as_view(), name="user_onboarding"),
    path("onboarding/approvals/", OnboardingApprovalListView.as_view(), name="user_onboarding_approvals"),
    path("accounts/manage/", RedirectView.as_view(pattern_name="user_division_account_roles", permanent=False)),
    path("accounts/manage/roles/", DivisionAccountRoleManageView.as_view(), name="user_division_account_roles"),
    path("accounts/manage/approvals/", OnboardingApprovalListView.as_view(), name="user_account_approvals"),
    path("api/v1/users/roles/assignable/", AssignableRoleOptionsApiView.as_view(), name="api_user_assignable_roles"),
    # 외부 서버 연동 (서비스 키 X-JCC-Integration-Key)
    path("api/v1/integration/ping/", IntegrationPingView.as_view(), name="api_integration_ping"),
    path(
        "api/v1/integration/verify-token/",
        IntegrationVerifyTokenView.as_view(),
        name="api_integration_verify_token",
    ),
    path(
        "api/v1/integration/users/<int:user_id>/",
        IntegrationUserDetailView.as_view(),
        name="api_integration_user_detail",
    ),
    path(
        "api/v1/integration/permissions/check/",
        IntegrationPermissionCheckView.as_view(),
        name="api_integration_permissions_check",
    ),
    path(
        "api/v1/integration/debug/issue-token/",
        IntegrationIssueTokenDebugView.as_view(),
        name="api_integration_debug_issue_token",
    ),
]
