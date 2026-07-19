"""공지사항·타임테이블 템플릿 페이지."""

from __future__ import annotations

from collections import OrderedDict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q
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
from users.mixins import NoticeManageRequiredMixin, NoticeReadAccessRequiredMixin
from users.models import Division, Region
from users.permissions import is_notice_manager


def _can_manage_notices(user) -> bool:
    """공지 작성·수정·삭제 권한: 슈퍼유저·플랫폼 관리자(is_staff)·공지 관리 기능권한."""
    return is_notice_manager(user)


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


def _categories_context():
    categories = list(Notice.active_categories())
    return {"categories": categories}


class NoticeFormContextMixin:
    """작성/수정 폼에서 지역·부서·카테고리 선택에 필요한 컨텍스트."""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_org_context())
        ctx.update(_categories_context())
        ctx["notices_tab"] = "create"
        instance = getattr(self, "object", None)
        ctx["selected_region_id"] = (
            instance.division.region_id if instance and instance.division_id else ""
        )
        return ctx


class NoticeListView(LoginRequiredMixin, NoticeReadAccessRequiredMixin, ListView):
    model = Notice
    template_name = "notices/notice_list.html"
    context_object_name = "notices"
    login_url = reverse_lazy("user_login")
    paginate_by = 12

    def _list_filters(self):
        q = (self.request.GET.get("q") or "").strip()
        category_slug = (self.request.GET.get("category") or "").strip()
        return q, category_slug

    def get_queryset(self):
        qs = Notice.visible_queryset()
        q, category_slug = self._list_filters()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
        if category_slug:
            qs = qs.filter(category__slug=category_slug, category__is_active=True)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage_notices"] = _can_manage_notices(self.request.user)
        ctx["notices_tab"] = "notices"
        q, category_slug = self._list_filters()
        ctx["q"] = q
        ctx["selected_category"] = category_slug
        ctx.update(_categories_context())
        return ctx


class NoticeDetailView(LoginRequiredMixin, NoticeReadAccessRequiredMixin, DetailView):
    model = Notice
    template_name = "notices/notice_detail.html"
    context_object_name = "notice"
    login_url = reverse_lazy("user_login")

    def get_queryset(self):
        return Notice.objects.select_related(
            "created_by", "division", "division__region", "category"
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        Notice.objects.filter(pk=obj.pk).update(view_count=F("view_count") + 1)
        obj.view_count += 1
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        notice = self.object
        ctx["can_manage_notices"] = _can_manage_notices(self.request.user)
        ctx["notices_tab"] = "notices"
        base_qs = Notice.visible_queryset().order_by("-is_pinned", "-created_at", "-id")
        # 목록 정렬(-고정, -작성일) 기준: 다음글=위쪽(더 최신), 이전글=아래쪽(더 오래됨)
        ctx["next_notice"] = (
            base_qs.filter(
                Q(is_pinned__gt=notice.is_pinned)
                | Q(
                    is_pinned=notice.is_pinned,
                    created_at__gt=notice.created_at,
                )
                | Q(
                    is_pinned=notice.is_pinned,
                    created_at=notice.created_at,
                    pk__gt=notice.pk,
                )
            )
            .order_by("is_pinned", "created_at", "id")
            .first()
        )
        ctx["prev_notice"] = (
            base_qs.filter(
                Q(is_pinned__lt=notice.is_pinned)
                | Q(
                    is_pinned=notice.is_pinned,
                    created_at__lt=notice.created_at,
                )
                | Q(
                    is_pinned=notice.is_pinned,
                    created_at=notice.created_at,
                    pk__lt=notice.pk,
                )
            )
            .order_by("-is_pinned", "-created_at", "-id")
            .first()
        )
        return ctx


class NoticeCreateView(
    NoticeManageRequiredMixin, LoginRequiredMixin, NoticeFormContextMixin, CreateView
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
    NoticeManageRequiredMixin, LoginRequiredMixin, NoticeFormContextMixin, UpdateView
):
    model = Notice
    form_class = NoticeForm
    template_name = "notices/notice_form.html"
    login_url = reverse_lazy("user_login")
    success_url = reverse_lazy("notice_list")


class NoticeDeleteView(NoticeManageRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Notice
    template_name = "notices/notice_confirm_delete.html"
    login_url = reverse_lazy("user_login")
    success_url = reverse_lazy("notice_list")


class TimetableView(LoginRequiredMixin, NoticeReadAccessRequiredMixin, TemplateView):
    """수련회 타임테이블을 집회별로 보여주는 읽기 전용 화면.

    집회(RetreatEvent) 단위로 작성된 타임테이블을 드롭다운으로 선택해 조회한다.
    편집은 수련회 > 관리 > 타임테이블 화면에서 한다.
    """

    template_name = "notices/timetable.html"
    login_url = reverse_lazy("user_login")

    def get_context_data(self, **kwargs):
        from retreat.models import RetreatEvent

        ctx = super().get_context_data(**kwargs)

        events = list(
            RetreatEvent.objects.filter(is_active=True).order_by("-start_date", "-id")
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
