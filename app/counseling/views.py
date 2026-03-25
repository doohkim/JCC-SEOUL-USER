"""상담 템플릿 페이지."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from counseling.services.slots import counseling_request_detail_for_user
from users.mixins import OnboardingRequiredMixin
from users.permissions import can_access_counseling_manage_tab, can_access_counseling_tab


class CounselingHomeView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "counseling/home.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_counseling_tab(request.user):
            raise PermissionDenied("로그인이 필요합니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "apply")
        if tab == "manage" and not can_access_counseling_manage_tab(self.request.user):
            tab = "apply"
        ctx["counseling_tab"] = tab
        ctx["can_manage_counseling"] = can_access_counseling_manage_tab(self.request.user)
        return ctx


class CounselingRequestDetailView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "counseling/request_detail.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_counseling_tab(request.user):
            raise PermissionDenied("로그인이 필요합니다.")
        counseling_request_detail_for_user(user=request.user, public_id=kwargs["public_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        req = counseling_request_detail_for_user(user=self.request.user, public_id=self.kwargs["public_id"])
        ctx["counseling_request"] = req
        ctx["is_counselor"] = req.counselor_id == self.request.user.pk
        ctx["public_id"] = str(req.public_id)
        return ctx
