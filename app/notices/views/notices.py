"""공지사항·타임테이블 템플릿 페이지."""

from __future__ import annotations

from collections import OrderedDict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from notices.forms import NoticeForm
from notices.models import Notice, TimetableEntry
from users.mixins import SignupSubmittedRequiredMixin, SuperuserRequiredMixin


class NoticeListView(SignupSubmittedRequiredMixin, LoginRequiredMixin, ListView):
    model = Notice
    template_name = "notices/notice_list.html"
    context_object_name = "notices"
    login_url = reverse_lazy("user_login")
    paginate_by = 20

    def get_queryset(self):
        return Notice.objects.select_related("created_by").all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage_notices"] = self.request.user.is_superuser
        return ctx


class NoticeDetailView(SignupSubmittedRequiredMixin, LoginRequiredMixin, DetailView):
    model = Notice
    template_name = "notices/notice_detail.html"
    context_object_name = "notice"
    login_url = reverse_lazy("user_login")

    def get_queryset(self):
        return Notice.objects.select_related("created_by")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage_notices"] = self.request.user.is_superuser
        return ctx


class NoticeCreateView(SuperuserRequiredMixin, LoginRequiredMixin, CreateView):
    model = Notice
    form_class = NoticeForm
    template_name = "notices/notice_form.html"
    login_url = reverse_lazy("user_login")
    success_url = reverse_lazy("notice_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class NoticeUpdateView(SuperuserRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Notice
    form_class = NoticeForm
    template_name = "notices/notice_form.html"
    login_url = reverse_lazy("user_login")
    success_url = reverse_lazy("notice_list")


class NoticeDeleteView(SuperuserRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Notice
    template_name = "notices/notice_confirm_delete.html"
    login_url = reverse_lazy("user_login")
    success_url = reverse_lazy("notice_list")


class TimetableView(SignupSubmittedRequiredMixin, LoginRequiredMixin, ListView):
    model = TimetableEntry
    template_name = "notices/timetable.html"
    context_object_name = "entries"
    login_url = reverse_lazy("user_login")

    def get_queryset(self):
        return TimetableEntry.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        grouped: OrderedDict = OrderedDict()
        for entry in ctx["entries"]:
            grouped.setdefault(entry.day, []).append(entry)
        ctx["entries_by_day"] = grouped
        return ctx
