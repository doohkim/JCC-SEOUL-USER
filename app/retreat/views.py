"""수련회 UI 페이지 뷰 (모바일 우선)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, TemplateView, View

from retreat.forms import RetreatApplyForm, RetreatStaffApplicationForm
from retreat.models import (
    Lodging,
    LodgingRoom,
    RetreatAttendance,
    RetreatAttendee,
    RetreatChangeLog,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatPickup,
    RetreatSession,
    RetreatSessionAttendee,
    RetreatStaffApplication,
    RetreatTimetableEntry,
    StaffApplicationTrack,
)
from retreat.services.event_picker import (
    default_retreat_landing_url,
    inject_picker_context,
    retreat_event_for_user,
    set_last_retreat_event,
)
from retreat.services.staff_application import (
    eligible_groups_for_member,
    event_staff_status,
    has_retreat_operational_access,
    member_can_apply_to_event,
    primary_affiliation_for,
    staff_applicant_tier,
    staff_applicant_tier_label,
)
from retreat.services.changelog_format import humanize_change_logs
from retreat.services.changelog_query import (
    CHANGELOG_PAGE_SIZE,
    changelog_actors_for_event,
    changelog_queryset_for_event,
    parse_changelog_filters,
    parse_page,
)
from retreat.services.account_retired import (
    ACCOUNT_RETIRED_DISPLAY,
    can_view_retired_account_data,
    exclude_retired_attendees_q,
    is_retired_account_row,
    visible_attendees_for,
    visible_pickups_for,
)
from retreat.services.staff_capabilities import (
    AccessLevel,
    can_access_retreat_page,
    effective_capabilities,
)
from users.permissions import (
    can_access_retreat_staff_apply,
    can_access_retreat_tab,
    can_change_retreat_check_in,
    can_link_attendee_user,
    can_delete_retreat_pickup,
    can_manage_retreat_pickup,
    can_manage_retreat_pickup_location,
    can_manage_retreat_sessions,
    can_manage_staff,
    can_select_pickup_group,
    can_view_retreat_all,
    can_view_staff,
    can_access_retreat_admin,
    is_retreat_council,
    is_retreat_event_admin,
    is_retreat_group_leader,
    is_retreat_staff,
    retreat_pickup_group_ids_for,
    retreat_pickup_visible_group_ids_for,
    visible_retreat_groups_for,
    visible_retreat_sessions_for,
)


def safe_retreat_back_url(request, event_id: int) -> str:
    """조원 관리 화면 '관리 완료' 링크용 안전한 이전 URL.

    동일 호스트 + /retreat/ 경로만 허용. 그 외는 출석부 목록으로 폴백.
    """
    default = reverse("retreat_rosters", args=[event_id])
    referer = (request.META.get("HTTP_REFERER") or "").strip()
    if not referer:
        return default
    try:
        ref = urlparse(referer)
    except ValueError:
        return default
    host = request.get_host()
    if ref.netloc and ref.netloc != host:
        return default
    path = ref.path or ""
    if not path.startswith("/retreat/"):
        return default
    current = (request.path or "").rstrip("/")
    if path.rstrip("/") == current:
        return default
    if ref.query:
        return f"{path}?{ref.query}"
    return path


class _RetreatStaffApplyAccessMixin(LoginRequiredMixin):
    """로그인 + 가입 완료(참가 신청서 제출 가능)."""

    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_access_retreat_staff_apply(
            request.user
        ):
            raise PermissionDenied("참가 신청을 이용할 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)


class _RetreatEntryMixin(LoginRequiredMixin):
    """`/retreat/` 진입 — 운영진·조장 또는 참가 신청 가능 사용자."""

    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not (
            can_access_retreat_tab(request.user)
            or can_access_retreat_staff_apply(request.user)
        ):
            raise PermissionDenied("수련회 화면을 이용할 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)


class _RetreatAccessMixin(LoginRequiredMixin):
    """로그인 + 수련회 탭 접근 권한(수련회 회장단·목사·조장 등)."""

    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_access_retreat_tab(request.user):
            raise PermissionDenied("수련회 화면을 이용할 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)


def _inject_retreat_caps(ctx, user, event) -> None:
    caps = effective_capabilities(user, event)
    ctx["retreat_caps"] = caps
    ctx["can_manage_staff"] = caps.manage_staff
    ctx["can_view_staff"] = caps.view_staff
    ctx["can_link_attendee_user"] = caps.link_attendee_user
    ctx["can_show_dashboard_tab"] = caps.dashboard >= AccessLevel.VIEW
    ctx["can_show_groups_tab"] = caps.groups >= AccessLevel.VIEW
    ctx["can_show_pickup_tab"] = caps.pickup >= AccessLevel.VIEW
    ctx["can_show_lodging_tab"] = can_view_retreat_all(user, event)
    ctx["can_show_admin_tab"] = can_access_retreat_admin(user, event)


class _RetreatEventMixin(_RetreatAccessMixin):
    """집회 컨텍스트 공통."""

    retreat_page: str | None = None
    retreat_picker_tab: str | None = None

    def get_picker_tab(self) -> str:
        return self.retreat_picker_tab or self.retreat_page or "dashboard"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.retreat_page:
            event = get_object_or_404(RetreatEvent, pk=kwargs["event_id"])
            if not can_access_retreat_page(request.user, event, self.retreat_page):
                raise PermissionDenied("이 화면에 접근할 권한이 없습니다.")
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and kwargs.get("event_id") is not None:
            set_last_retreat_event(request.session, int(kwargs["event_id"]))
        return response

    def get_event(self) -> RetreatEvent:
        return get_object_or_404(RetreatEvent, pk=self.kwargs["event_id"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.get_event()
        user = self.request.user
        ctx["event"] = event
        ctx["is_retreat_council"] = bool(
            user.is_superuser or is_retreat_event_admin(user, event)
        )
        ctx["is_retreat_staff"] = is_retreat_staff(user, event)
        ctx["can_view_retreat_all"] = can_view_retreat_all(user, event)
        _inject_retreat_caps(ctx, user, event)
        ctx["retreat_event_id"] = event.id
        inject_picker_context(
            ctx,
            user,
            event,
            retreat_tab=self.get_picker_tab(),
        )
        return ctx


class _RetreatHubEventMixin(_RetreatStaffApplyAccessMixin):
    """허브·참가 신청 — 운영 capability 없이 활성 집회만."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and kwargs.get("event_id") is not None:
            set_last_retreat_event(request.session, int(kwargs["event_id"]))
        return response

    def get_event(self) -> RetreatEvent:
        return get_object_or_404(
            RetreatEvent,
            pk=self.kwargs["event_id"],
            is_active=True,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.get_event()
        user = self.request.user
        ctx["event"] = event
        ctx["hide_retreat_bottom_tabs"] = True
        ctx["has_operational_access"] = has_retreat_operational_access(user, event)
        inject_picker_context(ctx, user, event, retreat_tab="staff_apply")
        return ctx


class RetreatHomeView(_RetreatEntryMixin, TemplateView):
    """`/retreat/` — 기본 집회로 redirect (활성 집회 없으면 empty)."""

    template_name = "retreat/empty.html"

    def get(self, request, *args, **kwargs):
        event = retreat_event_for_user(request.user, request.session)
        if event is None:
            return super().get(request, *args, **kwargs)
        if has_retreat_operational_access(request.user, event):
            return redirect(default_retreat_landing_url(request.user, event))
        return redirect("retreat_staff_apply", event_id=event.id)


class RetreatStaffApplyView(_RetreatHubEventMixin, FormView):
    """운영진 참가 신청서."""

    template_name = "retreat/staff_apply.html"
    form_class = RetreatStaffApplicationForm

    def get(self, request, *args, **kwargs):
        event = get_object_or_404(RetreatEvent, pk=kwargs["event_id"], is_active=True)
        if event_staff_status(request.user, event) == "closed":
            return self.render_to_response(self.get_context_data())
        return super().get(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            event = get_object_or_404(
                RetreatEvent, pk=kwargs["event_id"], is_active=True
            )
            status = event_staff_status(request.user, event)
            if status == "assigned":
                if has_retreat_operational_access(request.user, event):
                    return redirect(default_retreat_landing_url(request.user, event))
                return redirect("retreat_home")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        event = self.get_event()
        status = event_staff_status(self.request.user, event)
        kw["event"] = event
        kw["user"] = self.request.user
        kw["read_only"] = status in ("pending", "approved")
        return kw

    def get_initial(self):
        initial = super().get_initial()
        user = self.request.user
        region, division = primary_affiliation_for(user)
        if region and division:
            initial.setdefault("region", region.id)
            initial.setdefault("division", division.id)
        application = (
            RetreatStaffApplication.objects.filter(
                event=self.get_event(),
                user=user,
                status__in=[
                    RetreatStaffApplication.Status.PENDING,
                    RetreatStaffApplication.Status.APPROVED,
                ],
            )
            .select_related("region", "division", "group")
            .order_by("-created_at", "-id")
            .first()
        )
        if application:
            initial.update(
                {
                    "region": application.region_id,
                    "division": application.division_id,
                    "application_track": application.application_track,
                    "group": application.group_id,
                    "group_role": application.group_role,
                }
            )
        else:
            initial.setdefault(
                "application_track", StaffApplicationTrack.GROUP_LEADERSHIP
            )
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.get_event()
        user = self.request.user
        status = event_staff_status(user, event)
        form = kwargs.get("form")
        tier = staff_applicant_tier(user)
        region, division = primary_affiliation_for(user)
        eligible_groups = eligible_groups_for_member(user, event)
        can_apply, apply_block_message = member_can_apply_to_event(
            user, event, eligible_groups=eligible_groups
        )

        ctx["staff_status"] = status
        ctx["read_only"] = status in ("pending", "approved")
        ctx["is_pastoral"] = (
            form.is_pastoral if form else tier in ("pastor", "evangelist")
        )
        ctx["applicant_tier"] = tier
        ctx["applicant_tier_label"] = staff_applicant_tier_label(tier)
        ctx["fixed_region_name"] = region.name if region else ""
        ctx["fixed_division_name"] = division.name if division else ""
        ctx["eligible_groups"] = eligible_groups
        ctx["can_submit_application"] = (
            can_apply and status == "open" and not ctx["read_only"]
        )
        ctx["apply_block_message"] = apply_block_message
        ctx["show_ineligible_card"] = (
            status in ("open", "rejected")
            and not ctx["read_only"]
            and tier == "member"
            and not can_apply
        )
        ctx["group_role_choices"] = list(RetreatGroupMembership.Role.choices)
        rejected = (
            RetreatStaffApplication.objects.filter(
                event=event,
                user=user,
                status=RetreatStaffApplication.Status.REJECTED,
            )
            .order_by("-reviewed_at", "-id")
            .first()
        )
        ctx["rejection_reason"] = rejected.rejection_reason if rejected else ""
        return ctx

    def form_valid(self, form):
        if event_staff_status(self.request.user, self.get_event()) != "open":
            raise PermissionDenied("신청을 제출할 수 없습니다.")
        try:
            form.save()
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(
            self.request,
            "신청이 접수되었습니다. 승인 후 운영 화면이 열립니다.",
        )
        return redirect("retreat_home")

    def post(self, request, *args, **kwargs):
        if event_staff_status(request.user, self.get_event()) != "open":
            raise PermissionDenied("신청을 제출할 수 없습니다.")
        return super().post(request, *args, **kwargs)


class RetreatStaffApplicationsView(_RetreatEventMixin, TemplateView):
    """관리 > 참가 신청 목록·승인."""

    template_name = "retreat/staff_applications.html"
    retreat_page = "admin"
    retreat_picker_tab = "staff_applications"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            event = get_object_or_404(RetreatEvent, pk=kwargs["event_id"])
            if not can_manage_staff(request.user, event):
                raise PermissionDenied("참가 신청 관리 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        from retreat.models import RetreatCouncilMembership

        ctx["admin_subtab"] = "staff_applications"
        ctx["council_role_choices"] = list(RetreatCouncilMembership.Role.choices)
        ctx["council_role_choices_json"] = json.dumps(
            list(RetreatCouncilMembership.Role.choices)
        )
        from retreat.models import RetreatGroupMembership

        ctx["group_role_choices_json"] = json.dumps(
            list(RetreatGroupMembership.Role.choices)
        )
        ctx["total_sessions"], ctx["overall_rate"] = _retreat_session_summary(
            self.request.user, event
        )
        return ctx


class RetreatDashboardView(_RetreatEventMixin, TemplateView):
    template_name = "retreat/dashboard.html"
    retreat_page = "dashboard"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        user = self.request.user
        sessions = list(
            visible_retreat_sessions_for(user, event)
            .select_related("created_by", "closed_by")
            .order_by("-created_at", "-id")
        )
        ctx["sessions"] = sessions
        ctx["sessions_json"] = json.dumps(
            [
                {
                    "id": s.id,
                    "name": s.name,
                    "occurs_at": s.occurs_at.isoformat() if s.occurs_at else None,
                    "status": s.status,
                    "status_display": s.get_status_display(),
                }
                for s in sessions
            ],
            ensure_ascii=False,
        )
        return ctx


class RetreatRostersView(_RetreatEventMixin, TemplateView):
    """출석부(세션) 목록."""

    template_name = "retreat/rosters.html"
    retreat_picker_tab = "rosters"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        user = self.request.user
        sessions = list(
            visible_retreat_sessions_for(user, event)
            .select_related("created_by", "closed_by")
            .order_by("-created_at", "-id")
        )
        ctx["sessions"] = sessions

        visible_groups = list(
            visible_retreat_groups_for(user, event)
            .select_related("region", "division")
            .order_by("order", "id")
        )
        ctx["visible_groups"] = visible_groups

        membership_group_ids = set(
            user.retreat_group_memberships.filter(group__event=event).values_list(
                "group_id", flat=True
            )
        )
        ctx["my_groups"] = [g for g in visible_groups if g.id in membership_group_ids]

        ctx["can_manage_sessions"] = ctx["is_retreat_council"]
        return ctx


def _retreat_session_summary(user, event):
    """관리 영역 공통 헤더 부제목용 (총 세션 수, 전체 출석률)."""
    session_ids = list(
        visible_retreat_sessions_for(user, event).values_list("id", flat=True)
    )
    total = len(session_ids)
    possible = RetreatSessionAttendee.objects.filter(session_id__in=session_ids).count()
    present = RetreatAttendance.objects.filter(
        enrollment__session_id__in=session_ids,
        status=RetreatAttendance.Status.PRESENT,
    ).count()
    rate = round((present / possible) * 100, 1) if possible else None
    return total, rate


class RetreatCouncilView(_RetreatEventMixin, TemplateView):
    """집회 운영진 명단·관리 페이지."""

    template_name = "retreat/council.html"
    retreat_page = "admin"
    retreat_picker_tab = "council"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            event = get_object_or_404(RetreatEvent, pk=kwargs["event_id"])
            if not can_access_retreat_admin(request.user, event):
                raise PermissionDenied("집회 운영진 페이지 접근 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        from users.models import Division, Region
        from retreat.services.staff_pool import event_staff_eligible_division_ids

        from retreat.models import (
            RetreatCouncilMembership,
            RetreatGroupMembership,
        )

        event_division_ids = list(event_staff_eligible_division_ids(event.id))
        ctx["role_choices"] = RetreatCouncilMembership.Role.choices
        ctx["group_role_choices"] = RetreatGroupMembership.Role.choices
        ctx["role_choices_json"] = list(RetreatCouncilMembership.Role.choices)
        ctx["group_role_choices_json"] = list(RetreatGroupMembership.Role.choices)
        divisions_qs = Division.objects.select_related("region").filter(
            id__in=event_division_ids
        )
        ctx["division_choices"] = list(
            divisions_qs.order_by("region__sort_order", "sort_order", "name")
        )
        region_ids = {d.region_id for d in ctx["division_choices"]}
        ctx["region_choices"] = list(
            Region.objects.filter(id__in=region_ids).order_by("sort_order", "name")
        )
        ctx["total_sessions"], ctx["overall_rate"] = _retreat_session_summary(
            self.request.user, event
        )
        return ctx


class RetreatTimetableView(_RetreatEventMixin, TemplateView):
    """수련회 타임테이블(일정표) 조회·관리 페이지."""

    template_name = "retreat/timetable.html"
    retreat_page = "admin"
    retreat_picker_tab = "timetable"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            event = get_object_or_404(RetreatEvent, pk=kwargs["event_id"])
            if not can_access_retreat_admin(request.user, event):
                raise PermissionDenied("타임테이블 페이지 접근 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        entries = list(
            event.timetable_entries.all().order_by(
                "day", "start_time", "sort_order", "id"
            )
        )
        # 일자별로 묶어서 노출.
        from itertools import groupby

        ctx["entries"] = entries
        ctx["entries_by_day"] = [
            {"day": day, "items": list(items)}
            for day, items in groupby(entries, key=lambda e: e.day)
        ]

        # 작성 폼 일자 옵션: 집회 시작~종료일.
        days = []
        cursor = event.start_date
        while cursor <= event.end_date:
            days.append(cursor)
            cursor += timedelta(days=1)
        ctx["event_days"] = days
        ctx["total_sessions"], ctx["overall_rate"] = _retreat_session_summary(
            self.request.user, event
        )
        return ctx


class RetreatPickupView(_RetreatEventMixin, TemplateView):
    """수련회 픽업(입회/출회) 정보 수집 페이지."""

    template_name = "retreat/pickup.html"
    retreat_page = "pickup"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        user = self.request.user
        tab = (self.request.GET.get("tab") or "arrival").strip()
        if tab not in (
            RetreatPickup.Direction.ARRIVAL,
            RetreatPickup.Direction.DEPARTURE,
            "all",
        ):
            tab = RetreatPickup.Direction.ARRIVAL
        ctx["active_pickup_tab"] = tab

        pickups_qs = visible_pickups_for(
            user,
            event.pickups.select_related("group", "region", "division"),
        )
        if tab == "all":
            # 전체 보기: 입회·출회를 함께 노출 (보기 전용, 열차 시각 기준 정렬)
            pickups_qs = pickups_qs.order_by("train_time", "id")
        else:
            pickups_qs = pickups_qs.filter(direction=tab).order_by("number", "id")

        # 날짜 필터: 파라미터 미지정이면 오늘 기준, 빈 값('')이면 전체 표시
        raw_date = self.request.GET.get("date")
        if raw_date is None:
            filter_date = timezone.localdate()
        elif raw_date.strip() == "":
            filter_date = None
        else:
            try:
                filter_date = date.fromisoformat(raw_date.strip())
            except ValueError:
                filter_date = timezone.localdate()
        if filter_date is not None:
            pickups_qs = pickups_qs.filter(train_time__date=filter_date)
        ctx["pickup_filter_date"] = filter_date.isoformat() if filter_date else ""

        can_select_group = can_select_pickup_group(user, event)
        if not can_select_group:
            group_ids = retreat_pickup_visible_group_ids_for(user, event)
            if group_ids:
                pickups_qs = pickups_qs.filter(group_id__in=group_ids)
            else:
                pickups_qs = pickups_qs.none()

        pickups = list(pickups_qs)
        # 픽업 대상 조원의 입실 상태 매핑 ((group_id, name) -> 조원)
        pickup_group_ids = {p.group_id for p in pickups if p.group_id}
        attendee_map: dict[tuple[int, str], RetreatAttendee] = {}
        if pickup_group_ids:
            attendee_qs = visible_attendees_for(
                user,
                RetreatAttendee.objects.filter(group_id__in=pickup_group_ids),
            )
            for a in attendee_qs.only(
                "group_id", "name", "check_in_status", "participation_status"
            ):
                attendee_map.setdefault((a.group_id, a.name), a)
        status_rank = {
            RetreatAttendee.CheckInStatus.PENDING: 0,
            RetreatAttendee.CheckInStatus.CHECKED_IN: 1,
            RetreatAttendee.CheckInStatus.CHECKED_OUT: 2,
        }
        for p in pickups:
            att = attendee_map.get((p.group_id, p.name))
            p.check_in_status = att.check_in_status if att else ""
            p.check_in_status_display = att.get_check_in_status_display() if att else ""
            p.account_retired = is_retired_account_row(p)
            p.account_retired_display = (
                ACCOUNT_RETIRED_DISPLAY if p.account_retired else ""
            )

        # 구분별 입실 상태 필터 (입회/출회 탭에서만 적용):
        # - 입회(arrival): 아직 입실 전(pending/미기록)인 대상만 노출 (입실·퇴실 제외)
        # - 출회(departure): 입실전·입실 노출 (퇴실만 제외) — 등록 eligibility와 동일
        # '전체' 탭은 숨김 없이 모든 픽업을 표시한다.
        def _visible_by_status(p) -> bool:
            att = attendee_map.get((p.group_id, p.name)) if p.group_id else None
            if att is not None and att.participation_status == (
                RetreatAttendee.ParticipationStatus.ABSENT
            ):
                return False
            st = p.check_in_status or ""
            if p.direction == RetreatPickup.Direction.ARRIVAL:
                return st in ("", RetreatAttendee.CheckInStatus.PENDING)
            if p.direction == RetreatPickup.Direction.DEPARTURE:
                return st in (
                    "",
                    RetreatAttendee.CheckInStatus.PENDING,
                    RetreatAttendee.CheckInStatus.CHECKED_IN,
                )
            return True

        if tab != "all":
            pickups = [p for p in pickups if _visible_by_status(p)]

        # 정렬: 1) 입실 상태(입실전 → 입실 → 퇴실) 2) 열차 시각
        pickups.sort(
            key=lambda p: (status_rank.get(p.check_in_status, 9), p.train_time)
        )
        ctx["pickups"] = pickups
        ctx["pickup_count"] = len(pickups)

        ctx["can_manage_pickup"] = can_manage_retreat_pickup(user, event, tab=tab)
        ctx["can_delete_pickup"] = can_delete_retreat_pickup(user, event)
        ctx["can_view_retired_account_data"] = can_view_retired_account_data(user)
        ctx["can_select_pickup_group"] = can_select_group
        # 회장단·슈퍼유저만 조를 직접 선택 (그 외에는 본인 조 자동 지정)
        if can_select_group:
            group_list = list(event.groups.order_by("order", "name"))
            leader_group_id = None
            leader_group_ids: list[int] = []
        else:
            leader_group_ids = list(
                event.groups.filter(id__in=retreat_pickup_group_ids_for(user, event))
                .order_by("order", "name", "id")
                .values_list("id", flat=True)
            )
            group_list = (
                list(
                    event.groups.filter(id__in=leader_group_ids).order_by(
                        "order", "name", "id"
                    )
                )
                if leader_group_ids
                else []
            )
            leader_group_id = leader_group_ids[0] if leader_group_ids else None
        ctx["group_choices"] = group_list
        ctx["leader_group_id"] = leader_group_id
        ctx["leader_group_ids"] = leader_group_ids
        from users.models import Division, Region

        ctx["region_choices"] = list(Region.objects.order_by("sort_order", "name"))
        ctx["division_choices"] = list(
            Division.objects.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )
        # 모달 캐스케이딩(지역→부서→조)·조원 자동완성용 데이터
        group_list = ctx["group_choices"]
        ctx["pickup_group_list_json"] = json.dumps(
            [
                {
                    "id": g.id,
                    "name": g.name,
                    "region_id": g.region_id,
                    "division_id": g.division_id,
                }
                for g in group_list
            ],
            ensure_ascii=False,
        )
        members_map: dict[int, list[dict]] = {}
        if group_list:
            from retreat.services.participation import participating_filter

            for a in visible_attendees_for(
                user,
                participating_filter(
                    RetreatAttendee.objects.filter(group__in=group_list)
                ),
            ).order_by("group_id", "sort_order", "name", "id"):
                members_map.setdefault(a.group_id, []).append(
                    {
                        "name": a.name,
                        "phone": a.phone or "",
                        "check_in_status": a.check_in_status or "",
                    }
                )
        ctx["pickup_group_members_json"] = json.dumps(members_map, ensure_ascii=False)
        ctx["can_manage_pickup_location"] = can_manage_retreat_pickup_location(
            user, event
        )
        pickup_locations = list(
            event.pickup_locations.order_by("sort_order", "name", "id")
        )
        ctx["pickup_location_choices_json"] = json.dumps(
            [{"id": loc.id, "name": loc.name} for loc in pickup_locations],
            ensure_ascii=False,
        )
        return ctx


class RetreatRosterCheckView(_RetreatEventMixin, TemplateView):
    """출석부 체크 화면."""

    template_name = "retreat/roster_check.html"
    retreat_picker_tab = "rosters"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = ctx["event"]
        session = get_object_or_404(
            visible_retreat_sessions_for(user, event).select_related(
                "created_by", "closed_by"
            ),
            pk=kwargs["session_id"],
        )
        group = get_object_or_404(RetreatGroup, pk=kwargs["group_id"], event=event)

        visible_ids = set(
            visible_retreat_groups_for(user, event).values_list("id", flat=True)
        )
        if group.id not in visible_ids:
            raise PermissionDenied("이 조에 접근할 권한이 없습니다.")

        can_mutate = bool(
            not session.is_closed
            and (
                user.is_superuser
                or is_retreat_group_leader(user, group)
                or is_retreat_council(user, event)
            )
        )

        from django.db.models import Case, IntegerField, Value, When

        from retreat.models import RetreatAttendee

        role_order = Case(
            When(member_role=RetreatAttendee.MemberRole.LEADER, then=Value(0)),
            When(member_role=RetreatAttendee.MemberRole.VICE_LEADER, then=Value(1)),
            When(member_role=RetreatAttendee.MemberRole.TEACHER, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
        check_in_order = Case(
            When(
                check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN, then=Value(0)
            ),
            When(check_in_status=RetreatAttendee.CheckInStatus.PENDING, then=Value(1)),
            When(
                check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT, then=Value(2)
            ),
            default=Value(3),
            output_field=IntegerField(),
        )
        attendees = list(
            session.enrollments.filter(source_group=group)
            .select_related("source_attendee")
            .order_by(role_order, check_in_order, "sort_order", "name", "id")
        )
        att_ids = [a.id for a in attendees]
        records_qs = RetreatAttendance.objects.filter(enrollment_id__in=att_ids)
        records_by_enrollment_id: dict[int, str] = {}
        for rec in records_qs:
            records_by_enrollment_id[rec.enrollment_id] = rec.status
        matrix: dict[int, str] = {
            attendee.id: records_by_enrollment_id.get(
                attendee.id, RetreatAttendance.Status.ABSENT
            )
            for attendee in attendees
        }

        ctx["session"] = session
        ctx["group"] = group
        ctx["attendees"] = attendees
        ctx["matrix"] = matrix
        ctx["matrix_json"] = json.dumps(matrix, ensure_ascii=False)
        ctx["can_mutate"] = can_mutate
        ctx["sessions"] = list(
            visible_retreat_sessions_for(user, event).order_by("-created_at", "-id")
        )
        return ctx


class RetreatResultsView(_RetreatEventMixin, TemplateView):
    template_name = "retreat/results.html"
    retreat_picker_tab = "results"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        sessions = list(
            visible_retreat_sessions_for(self.request.user, event).order_by(
                "-created_at", "-id"
            )
        )
        ctx["sessions"] = sessions
        return ctx


class RetreatGroupManageListView(_RetreatEventMixin, TemplateView):
    """출석부와 분리된 조·조원(입퇴실) 관리 — 조 목록."""

    template_name = "retreat/manage_groups.html"
    retreat_page = "groups"

    def get_context_data(self, **kwargs):
        from users.models import Division, Region
        from users.permissions import can_add_retreat_group
        from users.services.user_display import user_display_name

        from retreat.models import RetreatAttendee, RetreatGroupMembership

        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        from retreat.services.auto_check_in import apply_due_auto_transitions

        apply_due_auto_transitions(event_id=event.id)
        user = self.request.user
        from django.db.models import Prefetch

        from retreat.models import RetreatGroupScope

        retired_attendee_q = exclude_retired_attendees_q(prefix="attendees__")
        groups = list(
            visible_retreat_groups_for(user, event)
            .select_related("region", "division")
            .prefetch_related(
                Prefetch(
                    "extra_scopes",
                    queryset=RetreatGroupScope.objects.select_related(
                        "region", "division"
                    ),
                )
            )
            .annotate(
                attendee_count=Count(
                    "attendees",
                    filter=(
                        retired_attendee_q
                        if not can_view_retired_account_data(user)
                        else Q()
                    ),
                    distinct=True,
                ),
                participating_count=Count(
                    "attendees",
                    filter=(
                        retired_attendee_q
                        & ~Q(
                            attendees__participation_status=(
                                RetreatAttendee.ParticipationStatus.ABSENT
                            )
                        )
                        if not can_view_retired_account_data(user)
                        else ~Q(
                            attendees__participation_status=(
                                RetreatAttendee.ParticipationStatus.ABSENT
                            )
                        )
                    ),
                    distinct=True,
                ),
            )
            .order_by("order", "id")
        )

        # 조 카드 조장 표시 — 소속 명단 조장 우선, 없으면 운영진 membership(겸직 담당조).
        from collections import defaultdict

        from retreat.models import RetreatGroupMembership
        from retreat.services.attendee_ordering import resolve_group_card_leader_name

        leaders_by_group: dict[int, list[RetreatAttendee]] = defaultdict(list)
        leader_attendee_qs = visible_attendees_for(
            user,
            RetreatAttendee.objects.filter(
                group__in=groups, member_role=RetreatAttendee.MemberRole.LEADER
            ).only("group_id", "name", "check_in_status", "user_id", "id"),
        )
        for leader in leader_attendee_qs:
            leaders_by_group[leader.group_id].append(leader)

        memberships_by_group: dict[int, list[RetreatGroupMembership]] = defaultdict(
            list
        )
        for membership in RetreatGroupMembership.objects.filter(
            group__in=groups,
            role=RetreatGroupMembership.Role.LEADER,
        ).select_related("user", "user__profile"):
            memberships_by_group[membership.group_id].append(membership)

        for g in groups:
            g.leader_names = resolve_group_card_leader_name(
                leaders_by_group.get(g.id, []),
                memberships_by_group.get(g.id, []),
            )
        group_ids = [g.id for g in groups]
        participating_q = ~Q(
            participation_status=RetreatAttendee.ParticipationStatus.ABSENT
        )
        if group_ids:
            status_counts = visible_attendees_for(
                user,
                RetreatAttendee.objects.filter(group_id__in=group_ids),
            ).aggregate(
                count_total=Count("id"),
                count_participating=Count("id", filter=participating_q),
                count_absent=Count(
                    "id",
                    filter=Q(
                        participation_status=RetreatAttendee.ParticipationStatus.ABSENT
                    ),
                ),
                count_pending=Count(
                    "id",
                    filter=participating_q
                    & Q(check_in_status=RetreatAttendee.CheckInStatus.PENDING),
                ),
                count_checked_in=Count(
                    "id",
                    filter=participating_q
                    & Q(check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN),
                ),
                count_checked_out=Count(
                    "id",
                    filter=participating_q
                    & Q(check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT),
                ),
            )
        else:
            status_counts = {
                "count_total": 0,
                "count_participating": 0,
                "count_absent": 0,
                "count_pending": 0,
                "count_checked_in": 0,
                "count_checked_out": 0,
            }
        ctx.update(status_counts)

        ctx["groups"] = groups
        ctx["can_add_group"] = can_add_retreat_group(user, event)
        ctx["region_choices"] = list(Region.objects.order_by("sort_order", "name"))
        ctx["division_choices"] = list(
            Division.objects.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )
        ctx["group_role_choices"] = RetreatGroupMembership.Role.choices
        return ctx


class RetreatGroupManageView(_RetreatEventMixin, TemplateView):
    """단일 조 조원 명단 — 입퇴실 상태·시각 관리 (출석부 없음)."""

    template_name = "retreat/manage_group_detail.html"
    retreat_page = "groups"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = ctx["event"]
        from retreat.services.auto_check_in import apply_due_auto_transitions

        apply_due_auto_transitions(event_id=event.id)
        from django.db.models import Prefetch

        from retreat.models import RetreatGroupScope

        group = get_object_or_404(
            RetreatGroup.objects.prefetch_related(
                Prefetch(
                    "extra_scopes",
                    queryset=RetreatGroupScope.objects.select_related(
                        "region", "division"
                    ),
                )
            ),
            pk=kwargs["group_id"],
            event=event,
        )

        visible_ids = set(
            visible_retreat_groups_for(user, event).values_list("id", flat=True)
        )
        if group.id not in visible_ids:
            raise PermissionDenied("이 조에 접근할 권한이 없습니다.")

        from users.permissions import (
            can_manage_retreat_group_leaders,
            can_add_retreat_group,
        )
        from users.models import Division, Region

        from retreat.models import RetreatGroupMembership

        can_manage_leaders = can_manage_retreat_group_leaders(user, group)

        from retreat.apis._common import (
            user_can_delete_attendee,
            user_can_edit_attendee_details,
        )
        from retreat.models import RetreatAttendee
        from retreat.services.group_sync import sync_attendee_from_membership

        # 기존 운영진(멤버십)이 조원 명단에 없으면 즉시 동기화(누락 방지·idempotent).
        synced_user_ids = set(
            group.attendees.filter(user__isnull=False).values_list("user_id", flat=True)
        )
        for m in group.memberships.select_related("user", "user__profile"):
            if m.user_id not in synced_user_ids:
                sync_attendee_from_membership(m, changed_by=user)

        ctx["group"] = group
        ctx["can_add_group"] = can_add_retreat_group(user, event)
        ctx["can_manage_leaders"] = can_manage_leaders
        ctx["group_role_choices"] = RetreatGroupMembership.Role.choices
        ctx["region_choices"] = list(Region.objects.order_by("sort_order", "name"))
        ctx["division_choices"] = list(
            Division.objects.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )
        ctx["attendee_role_choices"] = RetreatAttendee.MemberRole.choices
        from retreat.services.attendee_ordering import order_attendees_for_member_list

        from retreat.services.check_in_stamps import (
            is_attendee_profile_locked,
            is_expected_check_in_locked,
            is_expected_check_out_locked,
            is_expected_timestamps_locked,
        )
        from retreat.services.lodging_stay import lodging_stay_display
        from retreat.services.participation import is_participating

        attendees = list(
            order_attendees_for_member_list(
                visible_attendees_for(
                    user,
                    group.attendees.select_related(
                        "lodging_room", "lodging_room__lodging", "user"
                    ),
                )
            )
        )
        for attendee in attendees:
            attendee.account_retired = is_retired_account_row(attendee)
            attendee.account_retired_display = (
                ACCOUNT_RETIRED_DISPLAY if attendee.account_retired else ""
            )
            attendee.expected_timestamps_locked = is_expected_timestamps_locked(
                attendee
            )
            attendee.profile_locked = is_attendee_profile_locked(attendee)
            attendee.expected_check_in_locked = is_expected_check_in_locked(
                attendee, user, group
            )
            attendee.expected_check_out_locked = is_expected_check_out_locked(
                attendee, user, group
            )
            attendee.can_delete = user_can_delete_attendee(
                user, group, attendee=attendee
            )
            attendee.lodging_stay_display = lodging_stay_display(attendee)
        ctx["attendees"] = attendees
        ctx["can_view_retired_account_data"] = can_view_retired_account_data(user)
        ctx["count_total"] = len(attendees)
        ctx["count_participating"] = sum(1 for a in attendees if is_participating(a))
        ctx["count_absent"] = sum(
            1
            for a in attendees
            if a.participation_status == RetreatAttendee.ParticipationStatus.ABSENT
        )
        participating = [a for a in attendees if is_participating(a)]
        ctx["count_pending"] = sum(
            1
            for a in participating
            if a.check_in_status == RetreatAttendee.CheckInStatus.PENDING
        )
        ctx["count_checked_in"] = sum(
            1
            for a in participating
            if a.check_in_status == RetreatAttendee.CheckInStatus.CHECKED_IN
        )
        ctx["count_checked_out"] = sum(
            1
            for a in participating
            if a.check_in_status == RetreatAttendee.CheckInStatus.CHECKED_OUT
        )
        ctx["participation_choices"] = RetreatAttendee.ParticipationStatus.choices
        caps = effective_capabilities(user, event)
        ctx["can_edit_attendee"] = user_can_edit_attendee_details(user, group)
        ctx["can_add_attendee"] = caps.add_attendee or is_retreat_group_leader(
            user, group
        )
        ctx["can_change_status"] = caps.change_check_in
        ctx["can_link_attendee_user"] = caps.link_attendee_user
        ctx["can_delete_attendee"] = user_can_delete_attendee(user, group)
        ctx["back_url"] = reverse("retreat_group_manage_list", args=[event.id])
        ctx["back_label"] = "조 목록"
        from retreat.services.lodging import (
            room_assignment_option,
            rooms_for_group_with_counts,
        )

        event_rooms = [
            room_assignment_option(room) for room in rooms_for_group_with_counts(group)
        ]
        ctx["event_rooms"] = event_rooms
        ctx["event_rooms_json"] = json.dumps(event_rooms)
        from retreat.services.travel_presets import (
            travel_display_label,
            travel_fixed_and_occurs_map,
            travel_preset_models_for_group,
            travel_presets_for_group,
        )

        travel_models = travel_preset_models_for_group(group)
        travel_presets = travel_presets_for_group(group)
        ctx["travel_presets"] = travel_presets
        ctx["travel_presets_json"] = json.dumps(travel_presets, ensure_ascii=False)
        _arr_fixed, arrival_occurs = travel_fixed_and_occurs_map(
            travel_models["arrival"]
        )
        _dep_fixed, departure_occurs = travel_fixed_and_occurs_map(
            travel_models["departure"]
        )
        for attendee in attendees:
            attendee.arrival_travel_label = travel_display_label(
                attendee.expected_check_in_at,
                arrival_occurs,
                is_custom=attendee.arrival_travel_is_custom,
            )
            attendee.departure_travel_label = travel_display_label(
                attendee.expected_check_out_at,
                departure_occurs,
                is_custom=attendee.departure_travel_is_custom,
            )
        return ctx


class RetreatLodgingView(_RetreatEventMixin, TemplateView):
    """집회별 숙소·호실 CRUD 페이지."""

    template_name = "retreat/lodging.html"
    retreat_page = "lodging"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = ctx["event"]

        if not can_view_retreat_all(user, event):
            raise PermissionDenied("이 집회의 숙소를 볼 권한이 없습니다.")

        from django.db.models import Count, Prefetch

        from retreat.services.auto_check_in import apply_due_auto_transitions
        from retreat.services.lodging import room_has_vacancy
        from retreat.services.lodging_stats import build_lodging_page_summary
        from retreat.services.lodging_stay import (
            active_lodging_occupant_filter,
            active_lodging_occupant_q,
        )

        apply_due_auto_transitions(event_id=event.id)

        from users.models import Division, Region

        active_attendees_qs = active_lodging_occupant_filter(
            RetreatAttendee.objects.select_related("group")
        ).order_by("name", "id")
        rooms_qs = (
            LodgingRoom.objects.select_related("region", "division", "lodging")
            .annotate(
                assigned_count=Count(
                    "attendees", filter=active_lodging_occupant_q(prefix="attendees__")
                )
            )
            .prefetch_related(Prefetch("attendees", queryset=active_attendees_qs))
            .order_by("sort_order", "number", "id")
        )
        lodgings = list(
            Lodging.objects.filter(event=event)
            .select_related("region")
            .prefetch_related(Prefetch("rooms", queryset=rooms_qs))
            .order_by("sort_order", "name", "id")
        )
        for lodging in lodgings:
            for room in lodging.rooms.all():
                room.has_vacancy = room_has_vacancy(room)

        ctx["lodgings"] = lodgings
        ctx["lodging_summary"] = build_lodging_page_summary(event)
        ctx["can_manage_lodging"] = is_retreat_staff(user, event)
        ctx["lodging_subtab"] = "manage"
        ctx["room_gender_choices"] = LodgingRoom.Gender.choices
        ctx["region_choices"] = list(Region.objects.order_by("sort_order", "name"))
        ctx["division_choices"] = list(
            Division.objects.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )
        return ctx


class RetreatLodgingRosterView(_RetreatEventMixin, TemplateView):
    """집회 전체 조원 명단 — 입실·숙소 배정 필터 조회."""

    template_name = "retreat/lodging_roster.html"
    retreat_picker_tab = "lodging_roster"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = ctx["event"]

        if not can_view_retreat_all(user, event):
            raise PermissionDenied("이 집회의 숙소를 볼 권한이 없습니다.")

        from retreat.services.auto_check_in import apply_due_auto_transitions
        from retreat.services.lodging_roster import build_lodging_roster_context

        apply_due_auto_transitions(event_id=event.id)
        ctx.update(build_lodging_roster_context(event, user))
        from retreat.apis._common import user_can_edit_attendee_details
        from retreat.services.lodging import (
            room_assignment_option,
            rooms_for_group_with_counts,
        )

        attendees = ctx["roster_attendees"]
        group_rooms: dict[int, list[dict]] = {}
        roster_any_can_edit = False
        for attendee in attendees:
            can_edit = user_can_edit_attendee_details(user, attendee.group)
            attendee.can_edit_roster = can_edit
            if can_edit:
                roster_any_can_edit = True
            if attendee.group_id not in group_rooms:
                group_rooms[attendee.group_id] = [
                    room_assignment_option(room)
                    for room in rooms_for_group_with_counts(attendee.group)
                ]
        ctx["roster_any_can_edit"] = roster_any_can_edit
        ctx["roster_group_rooms_json"] = json.dumps(group_rooms)
        ctx["travel_presets_json"] = json.dumps(
            ctx.get("travel_presets") or {"arrival": [], "departure": []},
            ensure_ascii=False,
        )
        ctx["can_change_status"] = can_change_retreat_check_in(user, event)
        ctx["attendee_role_choices"] = RetreatAttendee.MemberRole.choices
        ctx["lodging_subtab"] = "roster"
        ctx["can_manage_lodging"] = is_retreat_staff(user, event)
        return ctx


class RetreatLodgingAssignRedirectView(_RetreatEventMixin, View):
    """구 방배정 URL → 숙소·호수 관리 리다이렉트."""

    def get(self, request, *args, **kwargs):
        event = self.get_event()
        if not can_view_retreat_all(request.user, event):
            raise PermissionDenied("이 집회의 숙소를 볼 권한이 없습니다.")
        return redirect(reverse("retreat_lodging", kwargs={"event_id": event.id}))


class RetreatApplyView(_RetreatEventMixin, FormView):
    """기존 사용자 수련회 참여 신청."""

    template_name = "retreat/apply.html"
    form_class = RetreatApplyForm

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["event"] = self.get_event()
        return kw

    def get_success_url(self):
        return reverse(
            "retreat_dashboard", kwargs={"event_id": self.kwargs["event_id"]}
        )

    def form_valid(self, form):
        profile = getattr(self.request.user, "profile", None)
        if profile is None:
            from users.mixins import ensure_user_profile

            profile = ensure_user_profile(self.request.user)
        event = self.get_event()
        profile.requested_retreat_participation = form.cleaned_data[
            "requested_retreat_participation"
        ]
        profile.requested_retreat_event = (
            event if profile.requested_retreat_participation else None
        )
        profile.requested_retreat_role = (
            form.cleaned_data.get("requested_retreat_role") or ""
            if profile.requested_retreat_participation
            else ""
        )
        profile.save(
            update_fields=[
                "requested_retreat_participation",
                "requested_retreat_event",
                "requested_retreat_role",
                "updated_at",
            ]
        )
        messages.success(self.request, "수련회 참여 신청이 저장되었습니다.")
        return super().form_valid(form)


class RetreatGroupDetailView(_RetreatAccessMixin, TemplateView):
    """[사용 중단] 조원 명단 관리 (기존 출석부 탭 화면).

    조 관리(retreat_group_manage) 화면으로 대체되어 더 이상 제공하지 않는다.
    URL 로 직접 접근하면 404(Not Found)를 반환한다.
    """

    template_name = "retreat/group_detail.html"

    def dispatch(self, request, *args, **kwargs):
        # 과거 출석부 탭 페이지는 사용 중단됨 → 조 관리 화면 사용.
        raise Http404("페이지를 찾을 수 없습니다.")

    # ------------------------------------------------------------------
    # [LEGACY · 비활성화] 아래 원본 로직은 참고용으로 주석(문자열) 처리한다.
    # ------------------------------------------------------------------
    _LEGACY_GET_CONTEXT_DATA = """
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = get_object_or_404(RetreatEvent, pk=kwargs["event_id"])
        group = get_object_or_404(RetreatGroup, pk=kwargs["group_id"], event=event)

        visible_ids = set(
            visible_retreat_groups_for(user, event).values_list("id", flat=True)
        )
        if group.id not in visible_ids:
            raise PermissionDenied("이 조에 접근할 권한이 없습니다.")

        can_mutate = bool(
            user.is_superuser
            or is_retreat_group_leader(user, group)
            or is_retreat_staff(user, event)
        )
        can_manage_sessions = bool(can_manage_retreat_sessions(user, event))
        can_manage_attendees = can_mutate or can_manage_sessions

        from retreat.models import RetreatAttendee
        from retreat.services.enrollment import enroll_attendee_into_active_sessions

        sessions = list(
            visible_retreat_sessions_for(user, event).order_by("-created_at", "-id")
        )
        current_attendees = list(
            group.attendees.select_related("source_member", "user").order_by(
                "sort_order", "name", "id"
            )
        )
        # 조장·부조장 등 나중에 추가된 조원을 진행중 출석부에 자동 합류(idempotent).
        for attendee in current_attendees:
            enroll_attendee_into_active_sessions(attendee, actor=user)
        current_att_ids = [a.id for a in current_attendees]
        session_ids = [s.id for s in sessions]
        closed_session_ids = [s.id for s in sessions if s.is_closed]

        for attendee in current_attendees:
            attendee.row_key = attendee.id
            attendee.can_edit = True
            attendee.is_snapshot_only = False

        current_enrollments = list(
            RetreatSessionAttendee.objects.filter(
                source_attendee_id__in=current_att_ids,
                session_id__in=session_ids,
            ).select_related("session")
        )
        snapshot_only_enrollments = [
            enrollment
            for enrollment in RetreatSessionAttendee.objects.filter(
                source_group=group,
                session_id__in=closed_session_ids,
            )
            .select_related("session")
            .order_by("check_in_status", "sort_order", "name", "id")
            if enrollment.source_attendee_id not in current_att_ids
        ]
        for enrollment in snapshot_only_enrollments:
            enrollment.row_key = -enrollment.id
            enrollment.can_edit = can_manage_sessions
            enrollment.is_snapshot_only = True

        def _row_member_role(row) -> str:
            if hasattr(row, "member_role") and row.member_role:
                return row.member_role
            src = getattr(row, "source_attendee", None)
            if src is not None:
                return src.member_role or RetreatAttendee.MemberRole.MEMBER
            return RetreatAttendee.MemberRole.MEMBER

        def _row_sort_key(row):
            role = _row_member_role(row)
            role_rank = {
                RetreatAttendee.MemberRole.LEADER: 0,
                RetreatAttendee.MemberRole.VICE_LEADER: 1,
                RetreatAttendee.MemberRole.TEACHER: 2,
            }.get(role, 3)
            check_in_rank = {
                RetreatAttendee.CheckInStatus.CHECKED_IN: 0,
                RetreatAttendee.CheckInStatus.PENDING: 1,
                RetreatAttendee.CheckInStatus.CHECKED_OUT: 2,
            }.get(row.check_in_status, 3)
            return (role_rank, check_in_rank, row.sort_order, row.name, abs(row.row_key))

        rows = sorted([*current_attendees, *snapshot_only_enrollments], key=_row_sort_key)
        role_labels = dict(RetreatAttendee.MemberRole.choices)
        for row in rows:
            row.display_member_role = role_labels.get(
                _row_member_role(row), "조원"
            )
        row_keys = [row.row_key for row in rows]
        row_key_by_attendee_id = {attendee.id: attendee.row_key for attendee in current_attendees}
        row_key_by_enrollment_id = {
            enrollment.id: enrollment.row_key
            for enrollment in snapshot_only_enrollments
        }

        enrollments = [*current_enrollments, *snapshot_only_enrollments]
        enrollment_by_row_session = {}
        for enrollment in enrollments:
            row_key = row_key_by_attendee_id.get(enrollment.source_attendee_id)
            if row_key is None:
                row_key = row_key_by_enrollment_id.get(enrollment.id)
            if row_key is None:
                continue
            enrollment_by_row_session[(row_key, enrollment.session_id)] = enrollment

        records_qs = RetreatAttendance.objects.filter(
            enrollment__in=enrollments
        ).select_related("enrollment")
        matrix: dict[int, dict[int, str]] = {row_key: {} for row_key in row_keys}
        for rec in records_qs:
            enrollment = rec.enrollment
            row_key = row_key_by_attendee_id.get(enrollment.source_attendee_id)
            if row_key is None:
                row_key = row_key_by_enrollment_id.get(enrollment.id)
            if row_key is None:
                continue
            matrix.setdefault(row_key, {})[enrollment.session_id] = rec.status

        enrollment_ids_matrix: dict[int, dict[int, int]] = {row_key: {} for row_key in row_keys}
        missing_matrix: dict[int, dict[int, bool]] = {row_key: {} for row_key in row_keys}
        enrollment_check_in_matrix: dict[int, dict[int, str]] = {row_key: {} for row_key in row_keys}
        for row in rows:
            for session in sessions:
                enrollment = enrollment_by_row_session.get((row.row_key, session.id))
                if enrollment is None:
                    missing_matrix.setdefault(row.row_key, {})[session.id] = True
                    continue
                enrollment_ids_matrix.setdefault(row.row_key, {})[session.id] = enrollment.id
                enrollment_check_in_matrix.setdefault(row.row_key, {})[
                    session.id
                ] = enrollment.check_in_status

        ctx["event"] = event
        ctx["group"] = group
        ctx["sessions"] = sessions
        ctx["attendees"] = rows
        ctx["matrix"] = matrix
        ctx["enrollment_ids_matrix"] = enrollment_ids_matrix
        ctx["missing_matrix"] = missing_matrix
        ctx["enrollment_check_in_matrix"] = enrollment_check_in_matrix
        ctx["can_mutate"] = can_mutate
        ctx["can_manage_sessions"] = can_manage_sessions
        ctx["can_manage_attendees"] = can_manage_attendees
        ctx["retreat_event_id"] = event.id
        ctx["is_retreat_staff"] = bool(
            user.is_superuser or is_retreat_staff(user, event)
        )
        ctx["back_url"] = safe_retreat_back_url(self.request, event.id)
        ctx["back_label"] = "관리 완료"
        selected_session_id = self.request.GET.get("session_id")
        if selected_session_id:
            try:
                selected_session_id_int = int(selected_session_id)
            except (TypeError, ValueError):
                selected_session_id_int = None
            if selected_session_id_int in {session.id for session in sessions}:
                ctx["selected_session_id"] = selected_session_id_int
            elif sessions:
                ctx["selected_session_id"] = sessions[0].id
        elif sessions:
            ctx["selected_session_id"] = sessions[0].id
        return ctx
    """


class RetreatAdminView(_RetreatEventMixin, TemplateView):
    """변경 이력 등 관리 화면."""

    template_name = "retreat/admin.html"
    retreat_page = "admin"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            event = get_object_or_404(RetreatEvent, pk=kwargs["event_id"])
            if not can_access_retreat_admin(request.user, event):
                raise PermissionDenied("수련회 관리 화면 접근 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = ctx["event"]
        tab = (self.request.GET.get("tab") or "groups").strip()
        if tab not in ("sessions", "groups", "changelog"):
            tab = "groups"
        ctx["active_tab"] = tab

        visible_sessions = list(
            visible_retreat_sessions_for(user, event)
            .select_related("created_by", "closed_by")
            .order_by("-created_at", "-id")
        )
        visible_session_ids = [s.id for s in visible_sessions]
        total_session_count = len(visible_sessions)
        ctx["total_sessions"] = total_session_count

        all_present = RetreatAttendance.objects.filter(
            enrollment__session_id__in=visible_session_ids,
            status=RetreatAttendance.Status.PRESENT,
        ).count()
        all_possible = RetreatSessionAttendee.objects.filter(
            session_id__in=visible_session_ids,
        ).count()
        ctx["overall_rate"] = (
            round((all_present / all_possible) * 100, 1) if all_possible else None
        )

        if ctx["active_tab"] == "groups":
            groups_qs = (
                visible_retreat_groups_for(user, event)
                .select_related("region", "division")
                .prefetch_related("memberships__user", "attendees")
                .annotate(attendee_count=Count("attendees", distinct=True))
                .order_by("order", "id")
            )
            rows = []
            for g in groups_qs:
                leaders = list(g.memberships.all())
                possible = RetreatSessionAttendee.objects.filter(
                    source_group=g,
                    session_id__in=visible_session_ids,
                ).count()
                present_count = 0
                if possible:
                    present_count = RetreatAttendance.objects.filter(
                        enrollment__source_group=g,
                        enrollment__session_id__in=visible_session_ids,
                        status=RetreatAttendance.Status.PRESENT,
                    ).count()
                attendance_rate = (
                    round((present_count / possible) * 100, 1) if possible else None
                )
                rows.append(
                    {
                        "group": g,
                        "leaders": leaders,
                        "attendee_count": g.attendee_count,
                        "session_count": total_session_count,
                        "present_count": present_count,
                        "attendance_rate": attendance_rate,
                    }
                )
            ctx["rows"] = rows
        else:
            ctx["rows"] = []

        if ctx["active_tab"] == "sessions":
            visible_groups = list(
                visible_retreat_groups_for(user, event)
                .select_related("region", "division")
                .order_by("order", "id")
            )
            ctx["sessions"] = visible_sessions
            ctx["visible_groups"] = visible_groups
            membership_group_ids = set(
                user.retreat_group_memberships.filter(group__event=event).values_list(
                    "group_id", flat=True
                )
            )
            ctx["my_groups"] = [
                g for g in visible_groups if g.id in membership_group_ids
            ]
        else:
            ctx.setdefault("sessions", [])
            ctx.setdefault("visible_groups", [])
            ctx.setdefault("my_groups", [])

        if ctx["active_tab"] == "changelog":
            filters = parse_changelog_filters(self.request.GET)
            qs = changelog_queryset_for_event(event, **filters)
            paginator = Paginator(qs, CHANGELOG_PAGE_SIZE)
            page_obj = paginator.get_page(parse_page(self.request.GET))
            ctx["changelog_entries"] = humanize_change_logs(page_obj.object_list)
            ctx["changelog_page"] = page_obj
            ctx["changelog_filters"] = {
                "q": filters["q"],
                "date_from": (
                    filters["date_from"].isoformat() if filters["date_from"] else ""
                ),
                "date_to": filters["date_to"].isoformat() if filters["date_to"] else "",
                "actor": str(filters["actor_id"] or ""),
                "target_type": filters["target_type"],
                "action": filters["action"],
            }
            ctx["changelog_actors"] = changelog_actors_for_event(event)
            ctx["changelog_target_type_choices"] = RetreatChangeLog.TargetType.choices
            ctx["changelog_action_choices"] = RetreatChangeLog.Action.choices
            # pager 링크용: tab + 필터 유지, page 제외
            query = self.request.GET.copy()
            query["tab"] = "changelog"
            query.pop("page", None)
            ctx["changelog_querystring"] = query.urlencode()

        from retreat.models import RetreatGroupMembership

        ctx["role_choices"] = RetreatGroupMembership.Role.choices
        ctx["can_manage_sessions"] = ctx["is_retreat_council"]
        ctx["session_status_choices"] = RetreatSession.Status.choices

        # 출석부 생성 모달의 '연결할 집회' 후보 — 본인이 관리 권한을 가진 활성 집회.
        if ctx["can_manage_sessions"]:
            base = RetreatEvent.objects.filter(is_active=True)
            if user.is_superuser:
                creatable = base
            else:
                creatable = base.filter(council_memberships__user=user).distinct()
            ctx["creatable_events"] = list(creatable.order_by("-start_date", "-id"))
        return ctx
