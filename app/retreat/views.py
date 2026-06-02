"""수련회 UI 페이지 뷰 (모바일 우선)."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView, TemplateView

from retreat.forms import RetreatApplyForm
from retreat.models import (
    Lodging,
    LodgingRoom,
    RetreatAttendance,
    RetreatAttendee,
    RetreatChangeLog,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatSession,
    RetreatSessionAttendee,
)
from retreat.services.changelog_format import humanize_change_logs
from users.permissions import (
    can_access_retreat_tab,
    can_manage_retreat_sessions,
    is_retreat_council,
    is_retreat_group_leader,
    is_retreat_staff,
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


class _RetreatAccessMixin(LoginRequiredMixin):
    """로그인 + 수련회 탭 접근 권한(staff or 멤버십)."""

    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_access_retreat_tab(request.user):
            raise PermissionDenied("수련회 화면을 이용할 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)


def _retreat_dropdown_events(user) -> list[RetreatEvent]:
    """수련회 상단 행사 드롭다운에 노출할 행사 목록.

    `home` 카드 노출 기준과 동일: 활성 행사 중 사용자가 staff/회장단/슈퍼유저이거나
    소속 조가 보이는 행사만 포함한다.
    """
    candidates = list(
        RetreatEvent.objects.filter(is_active=True).order_by("-start_date", "-id")
    )
    result: list[RetreatEvent] = []
    for ev in candidates:
        if (
            user.is_superuser
            or is_retreat_council(user, ev)
            or is_retreat_staff(user, ev)
        ):
            result.append(ev)
            continue
        if visible_retreat_groups_for(user, ev).exists():
            result.append(ev)
    return result


class _RetreatEventMixin(_RetreatAccessMixin):
    """행사 컨텍스트 공통."""

    def get_event(self) -> RetreatEvent:
        return get_object_or_404(RetreatEvent, pk=self.kwargs["event_id"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.get_event()
        user = self.request.user
        ctx["event"] = event
        ctx["is_retreat_council"] = bool(
            user.is_superuser or is_retreat_council(user, event)
        )
        ctx["is_retreat_staff"] = bool(
            user.is_superuser
            or ctx["is_retreat_council"]
            or is_retreat_staff(user, event)
        )
        ctx["retreat_event_id"] = event.id
        available = _retreat_dropdown_events(user)
        if event not in available:
            available = [event, *available]
        ctx["available_events"] = available
        return ctx


class RetreatHomeView(_RetreatAccessMixin, TemplateView):
    """`/retreat/` — 활성 행사 1개면 대시보드로, 아니면 행사 카드."""

    template_name = "retreat/home.html"

    def get(self, request, *args, **kwargs):
        active = list(
            RetreatEvent.objects.filter(is_active=True).order_by("-start_date", "-id")
        )
        if len(active) == 1:
            return redirect("retreat_dashboard", event_id=active[0].id)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        events = RetreatEvent.objects.filter(is_active=True).order_by(
            "-start_date", "-id"
        )

        cards = []
        for ev in events:
            groups_qs = (
                visible_retreat_groups_for(user, ev)
                .select_related("region", "division")
                .annotate(attendee_count=Count("attendees", distinct=True))
                .order_by("region__sort_order", "division__sort_order", "order", "id")
            )
            groups = list(groups_qs)
            is_staff_or_council = bool(
                user.is_superuser
                or is_retreat_council(user, ev)
                or is_retreat_staff(user, ev)
            )
            # 조가 없어도 staff/회장단/슈퍼유저면 행사 카드 노출.
            if not groups and not is_staff_or_council:
                continue
            cards.append(
                {
                    "event": ev,
                    "groups": groups,
                    "is_staff_or_council": is_staff_or_council,
                }
            )

        ctx["event_cards"] = cards
        ctx["is_retreat_staff_any"] = any(
            is_retreat_staff(user, c["event"]) for c in cards
        )
        return ctx


class RetreatDashboardView(_RetreatEventMixin, TemplateView):
    template_name = "retreat/dashboard.html"

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
            .order_by("region__sort_order", "division__sort_order", "order", "id")
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


class RetreatCouncilView(_RetreatEventMixin, TemplateView):
    """수련회 회장단 명단·관리 페이지."""

    template_name = "retreat/council.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            event = get_object_or_404(RetreatEvent, pk=kwargs["event_id"])
            user = request.user
            if not (
                user.is_superuser
                or is_retreat_council(user, event)
                or is_retreat_staff(user, event)
            ):
                raise PermissionDenied("회장단 페이지 접근 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        memberships = list(
            event.council_memberships.select_related("user").order_by(
                "role", "user__username"
            )
        )
        ctx["memberships"] = memberships
        ctx["role_choices"] = RetreatCouncilMembership.Role.choices
        return ctx


class RetreatRosterCheckView(_RetreatEventMixin, TemplateView):
    """출석부 체크 화면."""

    template_name = "retreat/roster_check.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = ctx["event"]
        session = get_object_or_404(
            visible_retreat_sessions_for(user, event)
            .select_related("created_by", "closed_by"),
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
                or is_retreat_staff(user, event)
            )
        )

        # 입실 → 퇴실 순, 그 안에서 sort_order, name, id 순.
        attendees = list(
            session.enrollments.filter(source_group=group).order_by(
                "check_in_status", "sort_order", "name", "id"
            )
        )
        att_ids = [a.id for a in attendees]
        records_qs = RetreatAttendance.objects.filter(
            enrollment_id__in=att_ids
        )
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        sessions = list(
            visible_retreat_sessions_for(self.request.user, event)
            .order_by("-created_at", "-id")
        )
        ctx["sessions"] = sessions
        return ctx


class RetreatGroupManageListView(_RetreatEventMixin, TemplateView):
    """출석부와 분리된 조·조원(입퇴실) 관리 — 조 목록."""

    template_name = "retreat/manage_groups.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = ctx["event"]
        user = self.request.user
        groups = list(
            visible_retreat_groups_for(user, event)
            .select_related("region", "division")
            .annotate(attendee_count=Count("attendees", distinct=True))
            .order_by("region__sort_order", "division__sort_order", "order", "id")
        )
        ctx["groups"] = groups
        return ctx


class RetreatGroupManageView(_RetreatEventMixin, TemplateView):
    """단일 조 조원 명단 — 입퇴실 상태·시각 관리 (출석부 없음)."""

    template_name = "retreat/manage_group_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = ctx["event"]
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
        can_edit_timestamps = bool(
            user.is_superuser
            or is_retreat_council(user, event)
            or is_retreat_staff(user, event)
        )

        ctx["group"] = group
        ctx["attendees"] = list(
            group.attendees.select_related("lodging_room", "lodging_room__lodging")
            .order_by("check_in_status", "sort_order", "name", "id")
        )
        ctx["can_mutate"] = can_mutate
        ctx["can_edit_timestamps"] = can_edit_timestamps
        ctx["back_url"] = reverse("retreat_group_manage_list", args=[event.id])
        ctx["back_label"] = "조 목록"
        # 숙소 배정 드롭다운 옵션 — 조의 region+division 과 모두 일치하는 호실만.
        from retreat.services.lodging import rooms_for_event_region_division

        event_rooms = list(
            rooms_for_event_region_division(
                event, group.region_id, group.division_id
            )
        )
        ctx["event_rooms"] = event_rooms
        return ctx


class RetreatLodgingView(_RetreatEventMixin, TemplateView):
    """행사별 숙소·호실 CRUD 페이지."""

    template_name = "retreat/lodging.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = ctx["event"]

        # 조회 권한: visible_retreat_groups_for 또는 staff/council/superuser.
        visible_groups = visible_retreat_groups_for(user, event)
        if not (
            user.is_superuser
            or is_retreat_council(user, event)
            or is_retreat_staff(user, event)
            or visible_groups.exists()
        ):
            raise PermissionDenied("이 행사의 숙소를 볼 권한이 없습니다.")

        from django.db.models import Prefetch

        rooms_qs = (
            LodgingRoom.objects.select_related("region", "division")
            .prefetch_related(
                Prefetch(
                    "attendees",
                    queryset=RetreatAttendee.objects.select_related("group").order_by(
                        "name", "id"
                    ),
                )
            )
            .order_by("sort_order", "number", "id")
        )
        lodgings = list(
            Lodging.objects.filter(event=event)
            .select_related("region")
            .prefetch_related(Prefetch("rooms", queryset=rooms_qs))
            .order_by("sort_order", "name", "id")
        )

        can_manage = bool(
            user.is_superuser
            or is_retreat_council(user, event)
            or is_retreat_staff(user, event)
        )

        from users.models import Division, Region

        ctx["lodgings"] = lodgings
        ctx["can_manage_lodging"] = can_manage
        ctx["room_gender_choices"] = LodgingRoom.Gender.choices
        ctx["region_choices"] = list(Region.objects.order_by("sort_order", "name"))
        ctx["division_choices"] = list(
            Division.objects.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )
        return ctx


class RetreatLodgingAssignView(_RetreatEventMixin, TemplateView):
    """호실 → 지역·부서 배정 페이지.

    각 호실의 `region`/`division` 을 지역·부서 카드 안에서 인라인으로 수정·해제할 수 있다.
    - 운영진(staff/council/superuser): 모든 호실 매핑을 변경 가능.
    - 조장/일반 조회자: 읽기 전용.

    조원 → 호실 직접 배정은 별도(조 관리) 페이지에서 처리한다.
    """

    template_name = "retreat/lodging_assign.html"

    def get_context_data(self, **kwargs):
        from collections import defaultdict

        from django.db.models import Prefetch

        from users.models import Division, Region

        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = ctx["event"]

        is_staff_like = bool(
            user.is_superuser
            or is_retreat_council(user, event)
            or is_retreat_staff(user, event)
        )
        visible_groups_qs = visible_retreat_groups_for(user, event).select_related(
            "region", "division"
        )
        if not (is_staff_like or visible_groups_qs.exists()):
            raise PermissionDenied("이 행사의 방배정 페이지 권한이 없습니다.")

        all_rooms = list(
            LodgingRoom.objects.filter(lodging__event=event)
            .select_related("lodging", "region", "division")
            .prefetch_related(
                Prefetch(
                    "attendees",
                    queryset=RetreatAttendee.objects.select_related("group").order_by(
                        "name", "id"
                    ),
                )
            )
            .order_by(
                "lodging__sort_order",
                "lodging__name",
                "sort_order",
                "number",
                "id",
            )
        )

        # (region_id, division_id) 별로 호실을 묶고, 둘 중 하나라도 비어있는 호실은
        # "미배정" 섹션으로 모은다.
        rooms_by_key: dict[tuple[int, int], list[LodgingRoom]] = defaultdict(list)
        unassigned_rooms: list[LodgingRoom] = []
        for room in all_rooms:
            if room.region_id is None or room.division_id is None:
                unassigned_rooms.append(room)
            else:
                rooms_by_key[(room.region_id, room.division_id)].append(room)

        # 행사에 존재하는 조의 (region, division) 조합은 호실이 0개여도 카드를
        # 노출한다 (운영진이 호실을 추가 배정할 수 있어야 하기 때문).
        group_combos = set(
            (g.region_id, g.division_id)
            for g in visible_groups_qs
            if g.region_id is not None and g.division_id is not None
        )

        # 호실의 기존 매핑도 빠짐없이 노출.
        room_combos = set(rooms_by_key.keys())
        combo_keys = group_combos | room_combos

        # region/division 객체 lookup.
        region_ids = {rid for rid, _ in combo_keys}
        division_ids = {did for _, did in combo_keys}
        region_map = {r.id: r for r in Region.objects.filter(id__in=region_ids)}
        division_map = {
            d.id: d
            for d in Division.objects.select_related("region").filter(
                id__in=division_ids
            )
        }

        # 지역 → 부서 카드 트리.
        region_buckets: dict[int, dict] = {}
        for region_id, division_id in combo_keys:
            region_obj = region_map.get(region_id)
            division_obj = division_map.get(division_id)
            if region_obj is None or division_obj is None:
                continue
            bucket = region_buckets.setdefault(
                region_id,
                {"region": region_obj, "divisions": []},
            )
            bucket["divisions"].append(
                {
                    "division": division_obj,
                    "rooms": rooms_by_key.get((region_id, division_id), []),
                }
            )

        # 정렬.
        for bucket in region_buckets.values():
            bucket["divisions"].sort(
                key=lambda d: (
                    d["division"].sort_order or 0,
                    d["division"].name,
                    d["division"].id,
                )
            )
        regions = sorted(
            region_buckets.values(),
            key=lambda b: (b["region"].sort_order or 0, b["region"].name, b["region"].id),
        )

        # 행사 외 지역/부서 모든 후보 — 미배정 호실에 지역/부서 지정용 select.
        all_regions = list(Region.objects.order_by("sort_order", "name"))
        all_divisions = list(
            Division.objects.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )

        ctx["regions"] = regions
        ctx["unassigned_rooms"] = unassigned_rooms
        ctx["all_regions"] = all_regions
        ctx["all_divisions"] = all_divisions
        ctx["is_staff_like"] = is_staff_like
        ctx["can_manage_lodging"] = is_staff_like
        return ctx


class RetreatApplyView(_RetreatEventMixin, FormView):
    """기존 사용자 수련회 참여 신청."""

    template_name = "retreat/apply.html"
    form_class = RetreatApplyForm

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["event"] = self.get_event()
        return kw

    def get_success_url(self):
        return reverse("retreat_dashboard", kwargs={"event_id": self.kwargs["event_id"]})

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
    """조원 명단 관리 (기존)."""

    template_name = "retreat/group_detail.html"

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

        sessions = list(
            visible_retreat_sessions_for(user, event).order_by("-created_at", "-id")
        )
        current_attendees = list(
            group.attendees.select_related("source_member").order_by(
                "check_in_status", "sort_order", "name", "id"
            )
        )
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

        rows = sorted(
            [*current_attendees, *snapshot_only_enrollments],
            key=lambda row: (
                row.check_in_status,
                row.sort_order,
                row.name,
                abs(row.row_key),
            ),
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


class RetreatAdminView(_RetreatEventMixin, TemplateView):
    """슈퍼유저·회장단·목사/전도사(read-only)만 접근. 그 외 staff는 차단."""

    template_name = "retreat/admin.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            event = get_object_or_404(RetreatEvent, pk=kwargs["event_id"])
            user = request.user
            role_code = getattr(getattr(user, "role_level", None), "code", "")
            allowed = (
                user.is_superuser
                or is_retreat_council(user, event)
                or role_code in {"pastor", "evangelist"}
            )
            if not allowed:
                raise PermissionDenied(
                    "수련회 관리 화면 접근 권한이 없습니다. "
                    f"(user={user.username}, is_superuser={user.is_superuser}, "
                    f"role_level={role_code or '-'}, "
                    f"council={is_retreat_council(user, event)})"
                )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        event = ctx["event"]
        tab = (self.request.GET.get("tab") or "sessions").strip()
        if tab not in ("sessions", "groups", "changelog"):
            tab = "sessions"
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
                .order_by(
                    "region__sort_order", "division__sort_order", "order", "id"
                )
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
                .order_by(
                    "region__sort_order", "division__sort_order", "order", "id"
                )
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
            changelog = list(
                RetreatChangeLog.objects.filter(event=event)
                .select_related("changed_by", "changed_by__profile")
                .order_by("-changed_at", "-id")[:200]
            )
            ctx["changelog_entries"] = humanize_change_logs(changelog)

        from retreat.models import RetreatGroupMembership

        ctx["role_choices"] = RetreatGroupMembership.Role.choices
        ctx["can_manage_sessions"] = ctx["is_retreat_council"]
        ctx["session_status_choices"] = RetreatSession.Status.choices

        # 출석부 생성 모달의 '연결할 행사' 후보 — 본인이 관리 권한을 가진 활성 행사.
        if ctx["can_manage_sessions"]:
            base = RetreatEvent.objects.filter(is_active=True)
            if user.is_superuser:
                creatable = base
            else:
                creatable = base.filter(council_memberships__user=user).distinct()
            ctx["creatable_events"] = list(
                creatable.order_by("-start_date", "-id")
            )
        else:
            ctx["creatable_events"] = []
        return ctx
