from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import urlencode
from django.db import transaction
from datetime import datetime, time, timedelta
import json
from django.views.generic import FormView, TemplateView

from users.mixins import ensure_user_profile, is_onboarding_complete
from users.models import (
    Division,
    FunctionalDepartment,
    Role,
    Team,
    User,
    UserDivisionTeam,
    UserFunctionalDeptRole,
    UserProfile,
)
from users.permissions import can_access_member_registry, is_platform_admin, pastoral_divisions_for
from users.services.user_display import kakao_nickname_map_for_user_ids, user_display_name


class KakaoAuthEntryView(TemplateView):
    template_name = "users/signup.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            profile = ensure_user_profile(request.user)
            if is_onboarding_complete(request.user, profile):
                return HttpResponseRedirect(reverse_lazy("attendance_dashboard"))
            return HttpResponseRedirect(reverse_lazy("user_onboarding"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        query = {"next": self.request.GET.get("next", "/attendance/?welcome=1")}
        ctx["kakao_begin_url"] = f"{reverse_lazy('social:begin', args=['kakao'])}?{urlencode(query)}"
        error = self.request.GET.get("error", "")
        error_reason = self.request.GET.get("error_reason", "")
        error_description = self.request.GET.get("error_description", "")

        error_message = ""
        if error:
            if error in {"access_denied", "permission_denied"}:
                error_message = "카카오 로그인 권한 동의가 취소되었습니다. 권한 동의 후 다시 시도해 주세요."
            elif error in {"invalid_request", "invalid_client", "server_error"}:
                error_message = "카카오 인증 요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
            elif error == "1":
                error_message = "카카오 로그인에 실패했습니다. 잠시 후 다시 시도해 주세요."
            else:
                error_message = "카카오 로그인에 실패했습니다. 다시 시도해 주세요."

        if not error_message and error_reason == "user_denied":
            error_message = "카카오 로그인 권한 동의가 취소되었습니다. 권한 동의 후 다시 시도해 주세요."

        if not error_message and error_description:
            error_message = f"카카오 인증 중 오류가 발생했습니다: {error_description}"

        ctx["login_error_message"] = error_message
        return ctx


class OnboardingRequestForm(forms.Form):
    requested_division = forms.ModelChoiceField(
        queryset=Division.objects.all().order_by("sort_order", "name"),
        label="희망 부서",
        empty_label="부서를 선택해 주세요",
    )
    requested_team = forms.ModelChoiceField(
        queryset=Team.objects.select_related("division").all().order_by("division__sort_order", "name"),
        label="희망 팀",
        required=False,
        empty_label="팀을 선택해 주세요 (선택)",
    )

    def clean(self):
        cleaned = super().clean()
        division = cleaned.get("requested_division")
        team = cleaned.get("requested_team")
        if team and division and team.division_id != division.id:
            self.add_error("requested_team", "선택한 팀은 해당 부서에 속하지 않습니다.")
        return cleaned


class UserOnboardingView(LoginRequiredMixin, FormView):
    template_name = "users/onboarding.html"
    form_class = OnboardingRequestForm
    login_url = reverse_lazy("user_login")
    success_url = reverse_lazy("user_onboarding")

    def dispatch(self, request, *args, **kwargs):
        profile = ensure_user_profile(request.user)
        if is_onboarding_complete(request.user, profile):
            target = request.GET.get("next") or reverse_lazy("attendance_dashboard")
            return HttpResponseRedirect(target)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        profile = ensure_user_profile(self.request.user)
        return {
            "requested_division": profile.requested_division_id,
            "requested_team": profile.requested_team_id,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = ensure_user_profile(self.request.user)
        ctx["onboarding_status"] = profile.onboarding_status
        ctx["onboarding_note"] = profile.onboarding_note
        ctx["requested_division_name"] = (
            profile.requested_division.name if profile.requested_division_id else ""
        )
        ctx["requested_team_name"] = profile.requested_team.name if profile.requested_team_id else ""
        ctx["is_pending_locked"] = bool(
            profile.onboarding_status == UserProfile.OnboardingStatus.PENDING
            and profile.requested_division_id
        )
        ctx["next_url"] = self.request.GET.get("next", "")
        teams_map = {}
        for t in Team.objects.select_related("division").order_by("division__sort_order", "sort_order", "name"):
            teams_map.setdefault(str(t.division_id), []).append({"id": t.id, "name": t.name})
        ctx["teams_map_json"] = json.dumps(teams_map, ensure_ascii=False)
        return ctx

    def form_valid(self, form):
        profile = ensure_user_profile(self.request.user)
        if profile.onboarding_status == UserProfile.OnboardingStatus.APPROVED:
            messages.info(self.request, "이미 승인된 계정입니다. 화면이 자동 갱신됩니다.")
            return HttpResponseRedirect(reverse_lazy("attendance_dashboard"))
        if (
            profile.onboarding_status == UserProfile.OnboardingStatus.PENDING
            and profile.requested_division_id
        ):
            messages.info(self.request, "이미 신청이 접수되어 승인 대기 중입니다.")
            return HttpResponseRedirect(self.get_success_url())

        profile.requested_division = form.cleaned_data["requested_division"]
        profile.requested_team = form.cleaned_data["requested_team"]
        profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        profile.onboarding_note = ""
        profile.save(
            update_fields=[
                "requested_division",
                "requested_team",
                "onboarding_status",
                "onboarding_note",
                "updated_at",
            ]
        )
        messages.success(self.request, "소속 신청이 접수되었습니다. 관리자 승인 후 이용 가능합니다.")
        return super().form_valid(form)


class UserLogoutView(TemplateView):
    """운영 사용자 로그아웃 엔드포인트."""

    def get(self, request, *args, **kwargs):
        logout(request)
        return HttpResponseRedirect(reverse_lazy("user_login"))


class OnboardingApprovalListView(LoginRequiredMixin, TemplateView):
    """목사/전도사/관리자용 가입 승인 페이지."""

    template_name = "users/onboarding_approvals.html"
    login_url = reverse_lazy("user_login")
    _list_limit = 500

    def dispatch(self, request, *args, **kwargs):
        if not can_access_member_registry(request.user):
            raise PermissionDenied("가입 승인 페이지 권한이 없습니다.")
        if not pastoral_divisions_for(request.user).exists():
            raise PermissionDenied("담당 부서가 없어 가입 승인을 이용할 수 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def _approval_list_redirect(self, request) -> str:
        q = {}
        for key in ("date_from", "date_to", "division_code"):
            v = (request.POST.get(key) or request.GET.get(key) or "").strip()
            if v:
                q[key] = v
        base = reverse("user_onboarding_approvals")
        return f"{base}?{urlencode(q)}" if q else base

    def _allowed_division_ids(self) -> set[int]:
        return set(pastoral_divisions_for(self.request.user).values_list("pk", flat=True))

    def _resolve_active_division(self):
        divisions = pastoral_divisions_for(self.request.user).order_by("sort_order", "name")
        if not divisions.exists():
            return None, divisions

        role_code = getattr(getattr(self.request.user, "role_level", None), "code", "")
        requested_code = (self.request.GET.get("division_code") or self.request.POST.get("division_code") or "").strip()
        if role_code == "pastor" or is_platform_admin(self.request.user):
            active = divisions.filter(code=requested_code).first() if requested_code else None
            if active is None:
                active = divisions.first()
            return active, divisions

        return divisions.first(), divisions

    def _parse_updated_at_range(self):
        """updated_at 기준 [start, end] 일 단위(현지). 기본 최근 90일."""
        today = timezone.localdate()
        raw_from = (self.request.GET.get("date_from") or "").strip()
        raw_to = (self.request.GET.get("date_to") or "").strip()
        if not raw_from and not raw_to:
            resolved_from = (today - timedelta(days=90)).isoformat()
            resolved_to = today.isoformat()
        elif not raw_from:
            resolved_to = raw_to or today.isoformat()
            resolved_from = resolved_to
        elif not raw_to:
            resolved_from = raw_from
            resolved_to = resolved_from
        else:
            resolved_from = raw_from
            resolved_to = raw_to

        try:
            start_date = datetime.strptime(resolved_from, "%Y-%m-%d").date()
        except ValueError:
            start_date = today - timedelta(days=90)
            resolved_from = start_date.isoformat()
        try:
            end_date = datetime.strptime(resolved_to, "%Y-%m-%d").date()
        except ValueError:
            end_date = today
            resolved_to = end_date.isoformat()

        if end_date < start_date:
            end_date = start_date
            resolved_to = end_date.isoformat()

        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
        end_exclusive = end_date + timedelta(days=1)
        end_dt = timezone.make_aware(datetime.combine(end_exclusive, time.min), tz)
        return start_dt, end_dt, resolved_from, resolved_to

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "").strip()
        profile_id = request.POST.get("profile_id", "").strip()
        next_url = self._approval_list_redirect(request)
        allowed_ids = self._allowed_division_ids()
        if not profile_id.isdigit():
            messages.error(request, "대상 정보가 올바르지 않습니다.")
            return HttpResponseRedirect(next_url)

        profile = (
            UserProfile.objects.select_related("user", "requested_division", "requested_team")
            .filter(pk=int(profile_id))
            .first()
        )
        if profile is None:
            messages.error(request, "대상 사용자를 찾을 수 없습니다.")
            return HttpResponseRedirect(next_url)

        division_id = (request.POST.get("requested_division_id") or "").strip()
        team_id = (request.POST.get("requested_team_id") or "").strip()
        if division_id.isdigit():
            division = Division.objects.filter(pk=int(division_id)).first()
            if division is None:
                messages.error(request, "선택한 부서를 찾을 수 없습니다.")
                return HttpResponseRedirect(next_url)
            if division.id not in allowed_ids:
                messages.error(request, "담당 부서가 아닌 소속은 지정할 수 없습니다.")
                return HttpResponseRedirect(next_url)
            profile.requested_division = division
            if team_id.isdigit():
                team = Team.objects.filter(pk=int(team_id)).first()
                if team and team.division_id == division.id:
                    profile.requested_team = team
                else:
                    profile.requested_team = None
            else:
                profile.requested_team = None
            profile.save(update_fields=["requested_division", "requested_team", "updated_at"])

        status_from_action = {
            "approve": UserProfile.OnboardingStatus.APPROVED,
            "reject": UserProfile.OnboardingStatus.REJECTED,
            "save": "",
            "update_status": "",
        }
        if action not in status_from_action:
            messages.error(request, "처리할 수 없는 요청입니다.")
            return HttpResponseRedirect(next_url)

        selected_status = status_from_action[action] or (request.POST.get("onboarding_status") or "").strip()
        allowed_statuses = {
            UserProfile.OnboardingStatus.PENDING,
            UserProfile.OnboardingStatus.APPROVED,
            UserProfile.OnboardingStatus.REJECTED,
        }
        if selected_status not in allowed_statuses:
            messages.error(request, "상태 선택 값이 올바르지 않습니다.")
            return HttpResponseRedirect(next_url)
        if not profile.requested_division_id:
            messages.error(request, "신청 부서를 먼저 지정해 주세요.")
            return HttpResponseRedirect(next_url)
        if profile.requested_division_id not in allowed_ids:
            messages.error(request, "담당 부서 신청 건만 수정할 수 있습니다.")
            return HttpResponseRedirect(next_url)

        note = (request.POST.get("note") or "").strip()

        if selected_status == UserProfile.OnboardingStatus.APPROVED:
            team = profile.requested_team
            if team and team.division_id != profile.requested_division_id:
                team = None
            UserDivisionTeam.objects.update_or_create(
                user=profile.user,
                division=profile.requested_division,
                defaults={"team": team, "is_primary": True, "sort_order": 0},
            )
            profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
            profile.onboarding_note = note
            profile.save(update_fields=["onboarding_status", "onboarding_note", "updated_at"])
            messages.success(request, f"{user_display_name(profile.user)} 계정 상태를 승인 완료로 저장했습니다.")
            return HttpResponseRedirect(next_url)

        if selected_status == UserProfile.OnboardingStatus.REJECTED:
            profile.onboarding_status = UserProfile.OnboardingStatus.REJECTED
            profile.onboarding_note = note or "소속 정보를 확인 후 다시 신청해 주세요."
            profile.save(update_fields=["onboarding_status", "onboarding_note", "updated_at"])
            messages.info(request, f"{user_display_name(profile.user)} 계정 상태를 반려로 저장했습니다.")
            return HttpResponseRedirect(next_url)

        profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        profile.onboarding_note = note
        profile.save(update_fields=["onboarding_status", "onboarding_note", "updated_at"])
        messages.success(request, f"{user_display_name(profile.user)} 계정 상태를 승인 대기로 저장했습니다.")
        return HttpResponseRedirect(next_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        active_division, allowed_divisions = self._resolve_active_division()
        start_dt, end_dt, date_from, date_to = self._parse_updated_at_range()

        role_code = getattr(getattr(self.request.user, "role_level", None), "code", "")
        ctx["can_choose_onboarding_division"] = role_code == "pastor" or is_platform_admin(self.request.user)
        ctx["allowed_divisions"] = list(allowed_divisions)
        ctx["active_division"] = active_division
        ctx["date_from"] = date_from
        ctx["date_to"] = date_to
        ctx["onboarding_status_choices"] = [
            (UserProfile.OnboardingStatus.PENDING, "승인 대기"),
            (UserProfile.OnboardingStatus.APPROVED, "승인 완료"),
            (UserProfile.OnboardingStatus.REJECTED, "반려"),
        ]

        scoped = (
            UserProfile.objects.select_related("user", "requested_division", "requested_team")
            .exclude(user__is_staff=True)
            .exclude(user__is_superuser=True)
        )
        if active_division is not None:
            scoped = scoped.filter(requested_division_id=active_division.id)

        pending_profiles = scoped.filter(onboarding_status=UserProfile.OnboardingStatus.PENDING).order_by(
            "-updated_at", "-id"
        )[: self._list_limit]

        history = scoped.filter(updated_at__gte=start_dt, updated_at__lt=end_dt)
        rejected_profiles = history.filter(onboarding_status=UserProfile.OnboardingStatus.REJECTED).order_by(
            "-updated_at", "-id"
        )[: self._list_limit]
        approved_profiles = history.filter(onboarding_status=UserProfile.OnboardingStatus.APPROVED).order_by(
            "-updated_at", "-id"
        )[: self._list_limit]

        user_ids = set()
        user_ids.update(pending_profiles.values_list("user_id", flat=True))
        user_ids.update(rejected_profiles.values_list("user_id", flat=True))
        user_ids.update(approved_profiles.values_list("user_id", flat=True))
        kakao_map = kakao_nickname_map_for_user_ids(user_ids)
        label_map = {}
        if user_ids:
            for u in User.objects.filter(pk__in=user_ids).select_related("profile"):
                label_map[u.id] = user_display_name(u, kakao_map=kakao_map)

        ctx["pending_profiles"] = pending_profiles
        ctx["rejected_profiles"] = rejected_profiles
        ctx["approved_profiles"] = approved_profiles
        ctx["user_label_map"] = label_map
        ctx["account_tab"] = "approvals"
        ctx["division_choices"] = list(allowed_divisions.order_by("sort_order", "name"))
        team_map = {}
        for t in Team.objects.select_related("division").order_by("division__sort_order", "sort_order", "name"):
            team_map.setdefault(str(t.division_id), []).append({"id": t.id, "name": t.name})
        ctx["teams_map_json"] = json.dumps(team_map, ensure_ascii=False)
        return ctx


class DivisionAccountRoleManageView(LoginRequiredMixin, TemplateView):
    """목사/전도사/관리자용 부서 계정 직책 관리."""

    template_name = "users/division_account_roles.html"
    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_member_registry(request.user):
            raise PermissionDenied("계정 직책 관리 페이지 권한이 없습니다.")
        if not pastoral_divisions_for(request.user).exists():
            raise PermissionDenied("담당 부서가 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def _resolve_active_division(self):
        divisions = pastoral_divisions_for(self.request.user).order_by("sort_order", "name")
        if not divisions.exists():
            return None, divisions

        role_code = getattr(getattr(self.request.user, "role_level", None), "code", "")
        requested_code = (self.request.GET.get("division_code") or "").strip()
        if role_code == "pastor":
            active = divisions.filter(code=requested_code).first() if requested_code else None
            if active is None:
                active = divisions.first()
            return active, divisions

        # 전도사 및 일반 관리자는 선택 UI 없이 첫 부서 고정
        return divisions.first(), divisions

    def _division_functional_department(self, division: Division):
        return FunctionalDepartment.objects.get_or_create(
            code=f"division_{division.code}",
            defaults={"name": f"{division.name} 운영", "division": division, "sort_order": 0},
        )[0]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        active_division, _ = self._resolve_active_division()
        if active_division is None:
            messages.error(request, "관리 가능한 부서가 없습니다.")
            return HttpResponseRedirect(reverse_lazy("user_division_account_roles"))

        user_id = (request.POST.get("user_id") or "").strip()
        team_id = (request.POST.get("team_id") or "").strip()
        valid_role_codes = set(Role.objects.values_list("code", flat=True))
        selected_role_codes = [c for c in request.POST.getlist("role_codes") if c in valid_role_codes]
        if not user_id.isdigit():
            messages.error(request, "대상 사용자를 선택해 주세요.")
            return HttpResponseRedirect(
                f"{reverse_lazy('user_division_account_roles')}?division_code={active_division.code}"
            )

        target_user = User.objects.filter(pk=int(user_id), is_active=True).first()
        if target_user is None:
            messages.error(request, "대상 사용자를 찾을 수 없습니다.")
            return HttpResponseRedirect(
                f"{reverse_lazy('user_division_account_roles')}?division_code={active_division.code}"
            )
        if not target_user.division_teams.filter(division=active_division).exists():
            messages.error(request, "선택한 부서 소속 계정만 수정할 수 있습니다.")
            return HttpResponseRedirect(
                f"{reverse_lazy('user_division_account_roles')}?division_code={active_division.code}"
            )

        selected_team = None
        if team_id:
            if not team_id.isdigit():
                messages.error(request, "팀 선택 값이 올바르지 않습니다.")
                return HttpResponseRedirect(
                    f"{reverse_lazy('user_division_account_roles')}?division_code={active_division.code}"
                )
            selected_team = Team.objects.filter(pk=int(team_id), division=active_division).first()
            if selected_team is None:
                messages.error(request, "선택한 팀을 찾을 수 없습니다.")
                return HttpResponseRedirect(
                    f"{reverse_lazy('user_division_account_roles')}?division_code={active_division.code}"
                )

        membership = (
            target_user.division_teams.filter(division=active_division)
            .order_by("-is_primary", "sort_order", "id")
            .first()
        )
        if membership:
            if membership.team_id != (selected_team.id if selected_team else None):
                membership.team = selected_team
                membership.save(update_fields=["team"])
        else:
            UserDivisionTeam.objects.create(
                user=target_user,
                division=active_division,
                team=selected_team,
                is_primary=True,
                sort_order=0,
            )

        # Admin·가입 승인은 UserProfile.requested_* 를 볼 때가 많아, 실제 소속 팀과 맞춘다.
        profile = ensure_user_profile(target_user)
        if profile.requested_division_id is None:
            profile.requested_division = active_division
            profile.requested_team = selected_team
            profile.save(update_fields=["requested_division", "requested_team", "updated_at"])
        elif profile.requested_division_id == active_division.id:
            profile.requested_team = selected_team
            profile.save(update_fields=["requested_team", "updated_at"])

        department = self._division_functional_department(active_division)
        role_by_code = {r.code: r for r in Role.objects.filter(code__in=selected_role_codes)}

        UserFunctionalDeptRole.objects.filter(
            user=target_user, functional_department=department
        ).exclude(role__code__in=selected_role_codes).delete()

        for role_code in selected_role_codes:
            role = role_by_code.get(role_code)
            if role is None:
                continue
            UserFunctionalDeptRole.objects.get_or_create(
                user=target_user,
                functional_department=department,
                role=role,
                defaults={"sort_order": role.sort_order},
            )
        messages.success(request, f"{user_display_name(target_user)} 계정의 직책을 저장했습니다.")
        return HttpResponseRedirect(
            f"{reverse_lazy('user_division_account_roles')}?division_code={active_division.code}"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        active_division, allowed_divisions = self._resolve_active_division()
        role_code = getattr(getattr(self.request.user, "role_level", None), "code", "")
        can_choose_division = role_code == "pastor" or self.request.user.is_staff or self.request.user.is_superuser

        users_payload = []
        if active_division:
            department = self._division_functional_department(active_division)
            user_qs = (
                User.objects.filter(division_teams__division=active_division, is_active=True)
                .select_related("role_level", "profile")
                .distinct()
                .order_by("username")
            )
            memberships: dict[int, int | None] = {}
            for row in (
                UserDivisionTeam.objects.filter(user__in=user_qs, division=active_division)
                .order_by("-is_primary", "sort_order", "id")
                .values("user_id", "team_id")
            ):
                if row["user_id"] in memberships:
                    continue
                memberships[row["user_id"]] = row["team_id"]
            role_links = UserFunctionalDeptRole.objects.filter(
                user__in=user_qs,
                functional_department=department,
            ).select_related("role")
            kakao_nickname_by_user = kakao_nickname_map_for_user_ids(
                user_qs.values_list("pk", flat=True)
            )
            role_map: dict[int, set[str]] = {}
            for link in role_links:
                role_map.setdefault(link.user_id, set()).add(link.role.code)
            for u in user_qs:
                try:
                    display_name = u.profile.display_name
                except Exception:
                    display_name = ""
                if not display_name:
                    display_name = kakao_nickname_by_user.get(u.id, "")
                users_payload.append(
                    {
                        "id": u.id,
                        "username": u.username,
                        "display_name": display_name,
                        "phone": getattr(getattr(u, "profile", None), "phone", "") or "",
                        "role_level_name": u.role_level.name if u.role_level_id else "-",
                        "team_id": memberships.get(u.id),
                        "assigned_role_codes": sorted(list(role_map.get(u.id, set()))),
                        "assigned_role_codes_json": json.dumps(
                            sorted(list(role_map.get(u.id, set()))), ensure_ascii=False
                        ),
                    }
                )

        ctx["allowed_divisions"] = list(allowed_divisions)
        ctx["active_division"] = active_division
        ctx["can_choose_division"] = can_choose_division
        ctx["users_payload"] = users_payload
        ctx["division_team_choices"] = list(
            Team.objects.filter(division=active_division).order_by("sort_order", "name")
        ) if active_division else []
        ctx["account_tab"] = "roles"
        ctx["role_options_api_url"] = reverse_lazy("api_user_assignable_roles")
        return ctx


class AssignableRoleOptionsApiView(LoginRequiredMixin, TemplateView):
    """직책(Role) 전체 목록. 출석/주차 등 권한 연동용 코드는 없을 때 자동 생성."""

    _bootstrap_role_codes = (
        ("president", "회장", 10),
        ("team_leader", "팀장", 41),
        ("cell_leader", "셀장", 42),
        ("attendance_admin", "출석부 관리자", 43),
        ("parking_admin", "주차장 관리자", 44),
    )
    login_url = reverse_lazy("user_login")

    def get(self, request, *args, **kwargs):
        if not can_access_member_registry(request.user):
            raise PermissionDenied("직책 목록 조회 권한이 없습니다.")
        for code, name_ko, order in self._bootstrap_role_codes:
            Role.objects.get_or_create(code=code, defaults={"name": name_ko, "sort_order": order})
        roles = list(Role.objects.order_by("sort_order", "name").values("code", "name"))
        return JsonResponse({"results": roles})
