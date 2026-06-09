"""공지사항·타임테이블 템플릿 페이지."""

from __future__ import annotations

from collections import OrderedDict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from notices.forms import NoticeForm
from notices.models import Notice
from users.mixins import SuperuserRequiredMixin
from users.models import Division, Region


def _org_context():
    """지역·부서 선택용 공통 컨텍스트(캐스케이드 JS 포함)."""
    regions = list(Region.objects.all())
    divisions = list(
        Division.objects.select_related("region").order_by(
            "region__sort_order", "sort_order", "name"
        )
    )
    return {
        "regions": regions,
        "divisions": divisions,
    }


class NoticeFormContextMixin:
    """작성/수정 폼에서 지역·부서 선택에 필요한 컨텍스트."""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_org_context())
        ctx["notices_tab"] = "create"
        instance = getattr(self, "object", None)
        ctx["selected_region_id"] = (
            instance.division.region_id
            if instance and instance.division_id
            else ""
        )
        return ctx


class NoticeListView(SuperuserRequiredMixin, LoginRequiredMixin, ListView):
    model = Notice
    template_name = "notices/notice_list.html"
    context_object_name = "notices"
    login_url = reverse_lazy("user_login")
    paginate_by = 20

    def _filter_ids(self):
        region_raw = (self.request.GET.get("region") or "").strip()
        division_raw = (self.request.GET.get("division") or "").strip()
        region_id = int(region_raw) if region_raw.isdigit() else None
        division_id = int(division_raw) if division_raw.isdigit() else None
        return region_id, division_id

    def get_queryset(self):
        region_id, division_id = self._filter_ids()
        return Notice.visible_queryset(region_id=region_id, division_id=division_id)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage_notices"] = self.request.user.is_superuser
        ctx["notices_tab"] = "notices"
        region_id, division_id = self._filter_ids()
        ctx["selected_region_id"] = region_id or ""
        ctx["selected_division_id"] = division_id or ""
        ctx.update(_org_context())
        return ctx


class NoticeDetailView(SuperuserRequiredMixin, LoginRequiredMixin, DetailView):
    model = Notice
    template_name = "notices/notice_detail.html"
    context_object_name = "notice"
    login_url = reverse_lazy("user_login")

    def get_queryset(self):
        return Notice.objects.select_related(
            "created_by", "division", "division__region"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage_notices"] = self.request.user.is_superuser
        ctx["notices_tab"] = "notices"
        return ctx


class NoticeCreateView(
    SuperuserRequiredMixin, LoginRequiredMixin, NoticeFormContextMixin, CreateView
):
    model = Notice
    form_class = NoticeForm
    template_name = "notices/notice_form.html"
    login_url = reverse_lazy("user_login")
    success_url = reverse_lazy("notice_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class NoticeUpdateView(
    SuperuserRequiredMixin, LoginRequiredMixin, NoticeFormContextMixin, UpdateView
):
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


class TimetableView(SuperuserRequiredMixin, LoginRequiredMixin, TemplateView):
    """수련회 타임테이블을 행사별로 보여주는 읽기 전용 화면.

    행사(RetreatEvent) 단위로 작성된 타임테이블을 드롭다운으로 선택해 조회한다.
    편집은 수련회 > 관리 > 타임테이블 화면에서 한다.
    """

    template_name = "notices/timetable.html"
    login_url = reverse_lazy("user_login")

    def get_context_data(self, **kwargs):
        from retreat.models import RetreatEvent

        ctx = super().get_context_data(**kwargs)

        events = list(
            RetreatEvent.objects.filter(is_active=True).order_by(
                "-start_date", "-id"
            )
        )
        if not events:
            events = list(RetreatEvent.objects.order_by("-start_date", "-id"))

        sel_raw = (self.request.GET.get("event") or "").strip()
        sel_id = int(sel_raw) if sel_raw.isdigit() else None
        selected = None
        if sel_id is not None:
            selected = next((e for e in events if e.id == sel_id), None)
        if selected is None and events:
            selected = events[0]

        grouped: OrderedDict = OrderedDict()
        if selected is not None:
            for entry in selected.timetable_entries.all().order_by(
                "day", "start_time", "sort_order", "id"
            ):
                grouped.setdefault(entry.day, []).append(entry)

        ctx["events"] = events
        ctx["selected_event"] = selected
        ctx["entries_by_day"] = grouped
        ctx["notices_tab"] = "timetable"
        return ctx
