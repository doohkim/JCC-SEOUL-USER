"""출석 UI 페이지."""

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
import json
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView
from datetime import datetime, timedelta, date

from attendance.models import ParkingPermitApplication, ParkingPermitWindow
from attendance.services.parking import (
    korea_today,
    parking_request_allowed_now,
    parking_windows_display,
)
from users.mixins import OnboardingRequiredMixin
from users.models import Team, User
from users.services.user_display import kakao_nickname_map_for_user_ids, user_display_name
from users.permissions import (
    can_access_attendance_roster,
    can_change_dashboard_division,
    is_platform_admin,
    is_parking_manager,
    membership_divisions_for,
    visible_teams_for,
)


def _parking_messages_from_validation_error(exc: DjangoValidationError) -> str:
    if getattr(exc, "error_dict", None):
        parts = []
        for v in exc.error_dict.values():
            if isinstance(v, list):
                parts.extend(str(x) for x in v)
            else:
                parts.append(str(v))
        return " ".join(parts) if parts else " ".join(str(m) for m in exc.messages)
    return " ".join(str(m) for m in exc.messages)


def _parking_messages_from_form(form: forms.Form) -> str:
    texts: list[str] = []
    for field, errors in form.errors.items():
        for e in errors:
            if field == "__all__":
                texts.append(str(e))
            else:
                texts.append(f"{field}: {e}")
    return " ".join(texts) if texts else "입력값을 확인해 주세요."


def _parking_apply_redirect_url(*, tab: str, list_date: date | None) -> str:
    base = reverse_lazy("parking_permit_apply")
    q = f"?tab={tab}"
    if list_date is not None:
        q += f"&date={list_date.isoformat()}"
    return f"{base}{q}"


PARKING_TIME_CHOICES = [("", "선택")] + [
    (f"{h:02d}:00", f"{h:02d}:00")
    for h in range(24)
]


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


class ParkingPermitWindowForm(forms.ModelForm):
    class Meta:
        model = ParkingPermitWindow
        fields = ["division", "weekday", "start_time", "end_time", "is_active"]
        labels = {
            "division": "부서",
            "weekday": "요일",
            "start_time": "시작",
            "end_time": "종료",
            "is_active": "사용",
        }
        widgets = {
            "division": forms.Select(attrs={"class": "jcc-parking-input"}),
            "weekday": forms.Select(attrs={"class": "jcc-parking-input"}),
            "start_time": forms.Select(choices=PARKING_TIME_CHOICES, attrs={"class": "jcc-parking-input"}),
            "end_time": forms.Select(choices=PARKING_TIME_CHOICES, attrs={"class": "jcc-parking-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "jcc-parking-checkbox"}),
        }


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

    def _apply_list_date(self) -> tuple[date, str]:
        raw = (self.request.GET.get("date") or "").strip()
        if raw:
            try:
                d = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                d = korea_today()
        else:
            d = korea_today()
        return d, d.isoformat()

    def _manager_scoped_divisions(self):
        """관리 목록: 본인 소속 부서만 (주차 관리자·운영자 공통)."""
        return membership_divisions_for(self.request.user)

    def _manager_scoped_teams(self, divisions_qs):
        user = self.request.user
        if not divisions_qs.exists():
            return Team.objects.all().select_related("division").order_by(
                "division__sort_order", "sort_order", "name"
            )
        team_qs = Team.objects.none()
        for div in divisions_qs:
            team_qs = team_qs | visible_teams_for(user, div)
        return team_qs.select_related("division").order_by(
            "division__sort_order", "sort_order", "name"
        )

    def _resolve_datetime_range(self, date_from: str, date_to: str):
        today = korea_today()
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
        tab = (request.POST.get("tab") or "apply").strip()
        if tab not in {"apply", "manage", "window"}:
            tab = "apply"
        list_date_post = (request.POST.get("list_date") or "").strip()
        try:
            redirect_list_date = (
                datetime.strptime(list_date_post, "%Y-%m-%d").date() if list_date_post else None
            )
        except ValueError:
            redirect_list_date = None

        if action in {"window_create", "window_delete"}:
            if not is_parking_manager(request.user):
                raise PermissionDenied("주차권 관리 페이지 권한이 없습니다.")
            scoped_divisions = self._manager_scoped_divisions()
            scoped_ids = set(scoped_divisions.values_list("id", flat=True))
            if action == "window_create":
                wform = ParkingPermitWindowForm(request.POST)
                if not wform.is_valid():
                    messages.error(request, _parking_messages_from_form(wform))
                    return HttpResponseRedirect(_parking_apply_redirect_url(tab="window", list_date=None))
                obj = wform.save(commit=False)
                if obj.division_id not in scoped_ids:
                    messages.error(request, "소속 부서의 신청 가능 시간만 설정할 수 있습니다.")
                    return HttpResponseRedirect(_parking_apply_redirect_url(tab="window", list_date=None))
                try:
                    obj.full_clean()
                    obj.save()
                except DjangoValidationError as exc:
                    messages.error(request, _parking_messages_from_validation_error(exc))
                    return HttpResponseRedirect(_parking_apply_redirect_url(tab="window", list_date=None))
                messages.success(request, "신청 가능 시간을 추가했습니다.")
                return HttpResponseRedirect(_parking_apply_redirect_url(tab="window", list_date=None))
            window_id = (request.POST.get("window_id") or "").strip()
            if not window_id.isdigit():
                messages.error(request, "요청 데이터를 찾을 수 없습니다.")
                return HttpResponseRedirect(_parking_apply_redirect_url(tab="window", list_date=None))
            win = ParkingPermitWindow.objects.filter(pk=int(window_id), division_id__in=scoped_ids).first()
            if not win:
                messages.error(request, "소속 부서의 신청 가능 시간만 삭제할 수 있습니다.")
                return HttpResponseRedirect(_parking_apply_redirect_url(tab="window", list_date=None))
            win.delete()
            messages.success(request, "신청 가능 시간을 삭제했습니다.")
            return HttpResponseRedirect(_parking_apply_redirect_url(tab="window", list_date=None))

        if action in {"delete", "edit"} and app_id.isdigit():
            app = self._user_applications().filter(pk=int(app_id)).first()
            if app is None:
                messages.error(request, "요청 데이터를 찾을 수 없습니다.")
                return HttpResponseRedirect(_parking_apply_redirect_url(tab=tab, list_date=redirect_list_date))
            if action == "delete":
                app.delete()
                messages.success(request, "주차권 신청을 삭제했습니다.")
                return HttpResponseRedirect(_parking_apply_redirect_url(tab=tab, list_date=redirect_list_date))
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
            except DjangoValidationError as exc:
                messages.error(request, _parking_messages_from_validation_error(exc))
                return HttpResponseRedirect(_parking_apply_redirect_url(tab=tab, list_date=redirect_list_date))
            except IntegrityError:
                messages.error(
                    request,
                    "이미 해당 날짜에 같은 차량번호로 신청되어 있습니다. 하루에 한 번만 신청할 수 있습니다.",
                )
                return HttpResponseRedirect(_parking_apply_redirect_url(tab=tab, list_date=redirect_list_date))
            messages.success(request, "차량번호를 수정했습니다.")
            return HttpResponseRedirect(_parking_apply_redirect_url(tab=tab, list_date=redirect_list_date))
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        membership = self._primary_membership()
        list_date_post = (self.request.POST.get("list_date") or "").strip()
        try:
            redirect_list_date = (
                datetime.strptime(list_date_post, "%Y-%m-%d").date() if list_date_post else None
            )
        except ValueError:
            redirect_list_date = None

        obj = form.save(commit=False)
        obj.user = self.request.user
        if membership:
            obj.division = membership.division
            obj.team = membership.team
        obj.status = ParkingPermitApplication.Status.SUBMITTED
        try:
            obj.full_clean()
            obj.save()
        except DjangoValidationError as exc:
            messages.error(self.request, _parking_messages_from_validation_error(exc))
            return HttpResponseRedirect(_parking_apply_redirect_url(tab="apply", list_date=redirect_list_date))
        except IntegrityError:
            messages.error(
                self.request,
                "이미 해당 날짜에 같은 차량번호로 신청되어 있습니다. 하루에 한 번만 신청할 수 있습니다.",
            )
            return HttpResponseRedirect(_parking_apply_redirect_url(tab="apply", list_date=redirect_list_date))
        messages.success(self.request, "주차권 신청이 접수되었습니다.")
        return HttpResponseRedirect(_parking_apply_redirect_url(tab="apply", list_date=redirect_list_date))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["parking_user_label_map"] = {}
        membership = self._primary_membership()
        tab = (self.request.GET.get("tab") or "apply").strip()
        is_manager = is_parking_manager(self.request.user)
        if tab not in {"apply", "manage", "window"}:
            tab = "apply"
        if tab in {"manage", "window"} and not is_manager:
            tab = "apply"

        ctx["my_division_name"] = membership.division.name if membership else "-"
        ctx["my_team_name"] = membership.team.name if membership and membership.team_id else "-"
        list_date_obj, list_date_iso = self._apply_list_date()
        ctx["list_date"] = list_date_iso
        ctx["list_date_display"] = list_date_obj.strftime("%Y/%m/%d")
        ctx["list_date_is_today"] = list_date_obj == korea_today()
        ctx["applications"] = (
            self._user_applications()
            .filter(permit_date=list_date_obj)
            .order_by("-created_at")
        )
        ctx["parking_tab"] = tab
        ctx["is_parking_manager"] = is_manager

        div_id_for_windows = membership.division_id if membership else None
        ctx["parking_windows"] = parking_windows_display(div_id_for_windows)
        can_now, win_msg = parking_request_allowed_now(div_id_for_windows)
        ctx["parking_can_apply_now"] = can_now
        ctx["parking_window_message"] = win_msg

        if is_manager:
            scoped_divisions = self._manager_scoped_divisions()
            scoped_teams = self._manager_scoped_teams(scoped_divisions)
            division_ids = list(scoped_divisions.values_list("pk", flat=True))
            if not division_ids:
                qs = ParkingPermitApplication.objects.none()
            else:
                manager_scope = Q(division_id__in=division_ids) | Q(
                    division__isnull=True,
                    user__division_teams__division_id__in=division_ids,
                )
                qs = (
                    ParkingPermitApplication.objects.select_related(
                        "user", "user__profile", "division", "team"
                    )
                    .filter(manager_scope)
                    .distinct()
                )
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
            qs = qs.filter(permit_date__gte=start_date, permit_date__lt=end_date_exclusive)
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
            ctx["window_form"] = ParkingPermitWindowForm()
            ctx["window_form"].fields["division"].queryset = scoped_divisions
            ctx["window_rows"] = ParkingPermitWindow.objects.filter(
                division_id__in=division_ids
            ).select_related("division").order_by("division__sort_order", "division__name", "weekday", "start_time")
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
