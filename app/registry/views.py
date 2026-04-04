from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from users.mixins import OnboardingRequiredMixin
from users.permissions import can_access_member_registry


class RegistryMemberListPageView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "registry/member_list.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_member_registry(request.user):
            raise PermissionDenied("교적부 페이지 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)


class RegistryMemberDetailPageView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "registry/member_detail.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_member_registry(request.user):
            raise PermissionDenied("교적부 페이지 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["member_id"] = kwargs.get("member_id")
        return ctx


class RegistryMemberCreatePageView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "registry/member_form.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_member_registry(request.user):
            raise PermissionDenied("교적부 페이지 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["mode"] = "create"
        ctx["member_id"] = None
        return ctx


class RegistryMemberEditPageView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "registry/member_form.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_member_registry(request.user):
            raise PermissionDenied("교적부 페이지 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["mode"] = "edit"
        ctx["member_id"] = kwargs.get("member_id")
        return ctx


class RegistryMemberFamilyPageView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    """멤버 가족(행) 전용 화면."""

    template_name = "registry/member_family.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_member_registry(request.user):
            raise PermissionDenied("교적부 페이지 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["member_id"] = kwargs.get("member_id")
        return ctx
