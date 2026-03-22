"""출석 대시보드 (로그인 필요)."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class AttendanceDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "attendance/dashboard.html"
    login_url = "/admin/login/"
