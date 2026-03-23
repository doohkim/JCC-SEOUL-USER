"""출석 UI 페이지."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.views.generic import TemplateView
import json


class AttendanceDashboardView(LoginRequiredMixin, TemplateView):
    """출석 조회 UI (정적 ``attendance/app.css`` · ``app.js``)."""

    template_name = "attendance/app.html"
    login_url = "/admin/login/"


class AttendanceRosterListView(LoginRequiredMixin, TemplateView):
    template_name = "attendance/roster_list.html"
    login_url = "/admin/login/"


class AttendanceRosterEditView(LoginRequiredMixin, TemplateView):
    template_name = "attendance/roster_edit.html"
    login_url = "/admin/login/"


class AttendanceTeamRosterCheckView(LoginRequiredMixin, TemplateView):
    """팀장 전용 탭 출석부(주일 다중선택 / 수·토 예/불)."""

    template_name = "attendance/team_roster_check.html"
    login_url = "/admin/login/"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user

        if u.is_superuser:
            ctx["team_leader_allowed_division_codes_json"] = "null"
            ctx["team_leader_is_superuser"] = True
            ctx["team_leader_is_superuser_json"] = "true"
        else:
            division_codes = (
                u.division_teams.filter(team__isnull=False)
                .values_list("division__code", flat=True)
                .distinct()
            )
            ctx["team_leader_allowed_division_codes_json"] = json.dumps(list(division_codes))
            ctx["team_leader_is_superuser"] = False
            ctx["team_leader_is_superuser_json"] = "false"

        ctx["attendance_team_roster_mypage_url"] = "/attendance/team/roster/my/"
        return ctx


class AttendanceTeamRosterMyPageView(LoginRequiredMixin, TemplateView):
    template_name = "attendance/team_roster_mypage.html"
    login_url = "/admin/login/"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        if not u.is_authenticated:
            raise PermissionDenied()

        memberships = (
            u.division_teams.select_related("division", "team")
            .order_by("-is_primary", "division__sort_order", "sort_order", "team_id")
        )
        # 템플릿에 넘길 간단한 형태만
        ctx["memberships"] = [
            {
                "division_code": m.division.code,
                "division_name": m.division.name,
                "team_id": m.team_id,
                "team_name": m.team.name if m.team_id else "",
                "is_primary": m.is_primary,
            }
            for m in memberships
            if m.team_id is not None
        ]
        return ctx
