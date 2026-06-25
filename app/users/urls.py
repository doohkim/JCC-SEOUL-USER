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
from users.apis.mobile_auth import KakaoMobileLoginView, MobileMeView
from users.views import (
    AssignableRoleOptionsApiView,
    DivisionAccountActivityLogView,
    DivisionAccountRoleManageView,
    KakaoAuthEntryView,
    OnboardingApplicationActivityLogView,
    OnboardingApplicationsListView,
    OnboardingApprovalListView,
    UserLogoutView,
    UserOnboardingView,
    UserProfileView,
)

urlpatterns = [
    path("login/", KakaoAuthEntryView.as_view(), name="user_login"),
    path("logout/", UserLogoutView.as_view(), name="user_logout"),
    path("signup/", RedirectView.as_view(pattern_name="user_login", permanent=False)),
    path("profile/", UserProfileView.as_view(), name="user_profile"),
    path("onboarding/", UserOnboardingView.as_view(), name="user_onboarding"),
    path(
        "accounts/manage/applications/",
        OnboardingApplicationsListView.as_view(),
        name="user_onboarding_applications",
    ),
    path(
        "accounts/manage/applications/activity-log/",
        OnboardingApplicationActivityLogView.as_view(),
        name="user_onboarding_application_activity_log",
    ),
    path(
        "onboarding/approvals/",
        RedirectView.as_view(pattern_name="user_onboarding_applications", permanent=False),
        name="user_onboarding_approvals",
    ),
    path("accounts/manage/", RedirectView.as_view(pattern_name="user_division_account_roles", permanent=False)),
    path("accounts/manage/roles/", DivisionAccountRoleManageView.as_view(), name="user_division_account_roles"),
    path(
        "accounts/manage/roles/activity-log/",
        DivisionAccountActivityLogView.as_view(),
        name="user_division_account_activity_log",
    ),
    path(
        "accounts/manage/approvals/",
        RedirectView.as_view(pattern_name="user_onboarding_applications", permanent=False),
        name="user_account_approvals",
    ),
    path("api/v1/users/roles/assignable/", AssignableRoleOptionsApiView.as_view(), name="api_user_assignable_roles"),
    # 모바일 앱 인증
    path("api/v1/auth/kakao/", KakaoMobileLoginView.as_view(), name="api_auth_kakao_mobile"),
    path("api/v1/auth/me/", MobileMeView.as_view(), name="api_auth_me"),
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
