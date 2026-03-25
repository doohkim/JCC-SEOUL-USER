"""출석 UI 페이지."""

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
import json
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView
from django.utils import timezone
from datetime import datetime, time, timedelta

from attendance.models import ParkingPermitApplication
from users.mixins import OnboardingRequiredMixin
from users.models import Division, Team, User
from users.services.user_display import kakao_nickname_map_for_user_ids, user_display_name
from users.permissions import (
    can_access_attendance_roster,
    can_change_dashboard_division,
    is_platform_admin,
    is_parking_manager,
)


class AttendanceDashboardView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    """출석 조회 UI (정적 ``attendance/app.css`` · ``app.js``)."""

    template_name = "attendance/app.html"
    login_url = reverse_lazy("user_login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["show_welcome"] = self.request.GET.get("welcome") == "1"
        ctx["welcome_name"] = user_display_name(self.request.user) or self.request.user.get_full_name()
        ctx["can_change_division_json"] = "true" if can_change_dashboard_division(self.request.user) else "false"
        return ctx


class AttendanceRosterListView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "attendance/roster_list.html"
    login_url = reverse_lazy("user_login")


class AttendanceRosterEditView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "attendance/roster_edit.html"
    login_url = reverse_lazy("user_login")


class AttendanceTeamRosterCheckView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    """팀장 전용 탭 출석부(주일 다중선택 / 수·토 예/불)."""

    template_name = "attendance/team_roster_check.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_attendance_roster(request.user):
            raise PermissionDenied("출석부 페이지 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user

        if is_platform_admin(u):
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


class AttendanceTeamRosterMyPageView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "attendance/team_roster_mypage.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_attendance_roster(request.user):
            raise PermissionDenied("출석부 페이지 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

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


class ParkingPermitApplicationForm(forms.ModelForm):
    class Meta:
        model = ParkingPermitApplication
        fields = ["vehicle_number"]
        labels = {"vehicle_number": "차량번호"}

    def clean_vehicle_number(self):
        return (self.cleaned_data.get("vehicle_number") or "").strip()


class ParkingPermitApplyView(OnboardingRequiredMixin, LoginRequiredMixin, FormView):
    template_name = "attendance/parking_apply.html"
    form_class = ParkingPermitApplicationForm
    login_url = reverse_lazy("user_login")
    success_url = reverse_lazy("parking_permit_apply")

    def _primary_membership(self):
        return (
            self.request.user.division_teams.select_related("division", "team")
            .order_by("-is_primary", "sort_order", "id")
            .first()
        )

    def _user_applications(self):
        return ParkingPermitApplication.objects.filter(user=self.request.user).select_related(
            "division", "team"
        )

    def _manager_scoped_divisions(self):
        user = self.request.user
        if is_platform_admin(user):
            return Division.objects.all().order_by("sort_order", "name")
        division_ids = user.division_teams.values_list("division_id", flat=True).distinct()
        return Division.objects.filter(pk__in=division_ids).order_by("sort_order", "name")

    def _manager_scoped_teams(self, divisions_qs):
        return Team.objects.filter(division__in=divisions_qs).order_by(
            "division__sort_order", "sort_order", "name"
        )

    def _resolve_datetime_range(self, date_from: str, date_to: str):
        today = timezone.localdate()
        default_date = today.isoformat()
        if not date_from and not date_to:
            start_date = today
            end_date_exclusive = today + timedelta(days=1)
            return start_date, default_date, default_date, end_date_exclusive

        resolved_from = date_from or date_to or default_date
        resolved_to = date_to or date_from or default_date
        try:
            start_date = datetime.strptime(resolved_from, "%Y-%m-%d").date()
        except ValueError:
            start_date = today
            resolved_from = default_date
        try:
            end_date = datetime.strptime(resolved_to, "%Y-%m-%d").date()
        except ValueError:
            end_date = start_date
            resolved_to = start_date.isoformat()

        if end_date < start_date:
            end_date = start_date
            resolved_to = start_date.isoformat()
        end_date_exclusive = end_date + timedelta(days=1)
        return start_date, resolved_from, resolved_to, end_date_exclusive

    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "").strip()
        app_id = (request.POST.get("application_id") or "").strip()
        if action in {"delete", "edit"} and app_id.isdigit():
            app = self._user_applications().filter(pk=int(app_id)).first()
            if app is None:
                messages.error(request, "요청 데이터를 찾을 수 없습니다.")
                return HttpResponseRedirect(self.success_url)
            if action == "delete":
                app.delete()
                messages.success(request, "주차권 신청을 삭제했습니다.")
                return HttpResponseRedirect(self.success_url)
            vehicle_number = (request.POST.get("vehicle_number") or "").strip()
            app.vehicle_number = vehicle_number
            membership = self._primary_membership()
            if membership:
                app.division = membership.division
                app.team = membership.team
            app.status = ParkingPermitApplication.Status.SUBMITTED
            try:
                app.full_clean()
                app.save()
            except Exception as exc:
                messages.error(request, f"수정에 실패했습니다: {exc}")
                return HttpResponseRedirect(self.success_url)
            messages.success(request, "차량번호를 수정했습니다.")
            return HttpResponseRedirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        membership = self._primary_membership()
        obj = form.save(commit=False)
        obj.user = self.request.user
        if membership:
            obj.division = membership.division
            obj.team = membership.team
        obj.status = ParkingPermitApplication.Status.SUBMITTED
        try:
            obj.full_clean()
            obj.save()
        except Exception as exc:
            messages.error(self.request, f"신청에 실패했습니다: {exc}")
            return HttpResponseRedirect(self.success_url)
        messages.success(self.request, "주차권 신청이 접수되었습니다.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["parking_user_label_map"] = {}
        membership = self._primary_membership()
        tab = (self.request.GET.get("tab") or "apply").strip()
        is_manager = is_parking_manager(self.request.user)
        if tab not in {"apply", "manage"}:
            tab = "apply"
        if tab == "manage" and not is_manager:
            tab = "apply"

        ctx["my_division_name"] = membership.division.name if membership else "-"
        ctx["my_team_name"] = membership.team.name if membership and membership.team_id else "-"
        ctx["applications"] = self._user_applications().order_by("-created_at")
        ctx["parking_tab"] = tab
        ctx["is_parking_manager"] = is_manager

        if is_manager:
            scoped_divisions = self._manager_scoped_divisions()
            scoped_teams = self._manager_scoped_teams(scoped_divisions)
            qs = ParkingPermitApplication.objects.select_related(
                "user", "user__profile", "division", "team"
            ).filter(division__in=scoped_divisions)
            division_code = (self.request.GET.get("division_code") or "").strip()
            team_id = (self.request.GET.get("team_id") or "").strip()
            search = (self.request.GET.get("q") or "").strip()
            date_from = (self.request.GET.get("date_from") or "").strip()
            date_to = (self.request.GET.get("date_to") or "").strip()
            if division_code:
                qs = qs.filter(division__code=division_code)
            if team_id.isdigit():
                qs = qs.filter(team_id=int(team_id))
            if search:
                qs = qs.filter(
                    Q(vehicle_number__icontains=search)
                    | Q(user__username__icontains=search)
                    | Q(user__profile__display_name__icontains=search)
                )
            start_date, resolved_date_from, resolved_date_to, end_date_exclusive = (
                self._resolve_datetime_range(date_from, date_to)
            )
            tz = timezone.get_current_timezone()
            start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
            end_dt = timezone.make_aware(datetime.combine(end_date_exclusive, time.min), tz)
            qs = qs.filter(created_at__gte=start_dt, created_at__lt=end_dt)
            manager_qs = qs.order_by("-created_at")
            ctx["manager_applications"] = manager_qs
            uid_set = set(manager_qs.values_list("user_id", flat=True))
            kmap = kakao_nickname_map_for_user_ids(uid_set)
            ctx["parking_user_label_map"] = {
                u.id: user_display_name(u, kakao_map=kmap)
                for u in User.objects.filter(pk__in=uid_set).select_related("profile")
            }
            ctx["division_options"] = list(
                scoped_divisions.values("code", "name").order_by("name")
            )
            ctx["team_options"] = list(
                scoped_teams.values("id", "name", "division__code").order_by("name")
            )
            ctx["division_code"] = division_code
            ctx["team_id"] = team_id
            ctx["q"] = search
            ctx["date_from"] = resolved_date_from
            ctx["date_to"] = resolved_date_to
        return ctx


class ParkingPermitAdminView(OnboardingRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "attendance/parking_admin.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not is_parking_manager(request.user):
            raise PermissionDenied("주차권 관리 페이지 권한이 없습니다.")
        q = self.request.META.get("QUERY_STRING", "")
        suffix = f"&{q}" if q else ""
        return HttpResponseRedirect(f"{reverse_lazy('parking_permit_apply')}?tab=manage{suffix}")
