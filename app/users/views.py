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
    Region,
    Role,
    Team,
    User,
    UserDivisionTeam,
    UserFunctionalDeptRole,
    UserProfile,
)
from users.permissions import (
    can_access_onboarding_approvals,
    can_manage_division_accounts,
    membership_divisions_for,
    onboarding_approval_divisions_for,
)
from users.validators import validate_korea_mobile_phone
from retreat.models import RetreatGroup
from users.services.user_display import kakao_nickname_map_for_user_ids, user_display_name


def prefer_own_division(user, divisions):
    """관리 가능 부서 중 본인 소속 부서를 우선 선택."""
    own_ids = membership_divisions_for(user).values_list("id", flat=True)
    preferred = divisions.filter(id__in=own_ids).first()
    return preferred or divisions.first()


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


class _DivisionWithRegionChoiceField(forms.ModelChoiceField):
    """부서 선택 라벨 앞에 지역명을 prefix 로 보여준다 ('서울 · 청년부')."""

    def label_from_instance(self, obj):
        try:
            region_name = obj.region.name if obj.region_id else ""
        except Exception:
            region_name = ""
        if region_name:
            return f"{region_name} · {obj.name}"
        return obj.name


class OnboardingRequestForm(forms.Form):
    real_name = forms.CharField(label="실명", max_length=50)
    phone = forms.CharField(
        label="휴대폰",
        max_length=30,
        validators=[validate_korea_mobile_phone],
    )
    requested_region = forms.ModelChoiceField(
        queryset=Region.objects.order_by("sort_order", "name"),
        label="지역",
        empty_label="지역을 선택해 주세요",
    )
    requested_division = forms.ModelChoiceField(
        queryset=Division.objects.select_related("region").order_by(
            "region__sort_order", "sort_order", "name"
        ),
        label="희망 부서",
        empty_label="부서를 선택해 주세요",
    )
    requested_team = forms.ModelChoiceField(
        queryset=Team.objects.select_related("division").all().order_by(
            "division__sort_order", "sort_order", "name"
        ),
        label="희망 팀",
        required=False,
        empty_label="팀을 선택해 주세요",
    )
    requested_retreat_participation = forms.BooleanField(
        label="수련회 참여",
        required=False,
    )
    requested_retreat_group = forms.ModelChoiceField(
        queryset=RetreatGroup.objects.none(),
        label="희망 조",
        required=False,
        empty_label="조를 선택해 주세요",
    )
    requested_retreat_role = forms.ChoiceField(
        label="수련회 희망 역할",
        choices=[
            ("participant", "참가자"),
            ("leader", "조장"),
            ("vice_leader", "부조장"),
        ],
        required=False,
        initial="participant",
    )

    def __init__(self, *args, active_retreat_event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_retreat_event = active_retreat_event
        if active_retreat_event:
            self.fields["requested_retreat_group"].queryset = RetreatGroup.objects.filter(
                event=active_retreat_event
            ).select_related("region", "division").order_by(
                "region__sort_order", "division__sort_order", "order", "id"
            )
        else:
            self.fields.pop("requested_retreat_participation", None)
            self.fields.pop("requested_retreat_group", None)
            self.fields.pop("requested_retreat_role", None)

    def clean(self):
        cleaned = super().clean()
        region = cleaned.get("requested_region")
        division = cleaned.get("requested_division")
        team = cleaned.get("requested_team")
        if division and region and division.region_id != region.id:
            self.add_error("requested_division", "선택한 부서는 해당 지역에 속해야 합니다.")
        if team and division and team.division_id != division.id:
            self.add_error("requested_team", "선택한 팀은 해당 부서에 속하지 않습니다.")
        participate = cleaned.get("requested_retreat_participation")
        retreat_group = cleaned.get("requested_retreat_group")
        if participate and self.active_retreat_event:
            if not retreat_group:
                self.add_error("requested_retreat_group", "수련회 참여 시 조를 선택해 주세요.")
            elif division and retreat_group.division_id != division.id:
                self.add_error(
                    "requested_retreat_group",
                    "선택한 조는 신청 부서·지역과 일치해야 합니다.",
                )
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

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        from retreat.models import RetreatEvent

        kw["active_retreat_event"] = (
            RetreatEvent.objects.filter(is_active=True).order_by("-start_date", "-id").first()
        )
        return kw

    def get_initial(self):
        profile = ensure_user_profile(self.request.user)
        initial = {
            "real_name": profile.real_name or "",
            "phone": profile.phone or "",
            "requested_division": profile.requested_division_id,
            "requested_team": profile.requested_team_id,
        }
        if profile.requested_division_id:
            try:
                initial["requested_region"] = profile.requested_division.region_id
            except Exception:
                pass
        from retreat.models import RetreatEvent

        if RetreatEvent.objects.filter(is_active=True).exists():
            initial["requested_retreat_participation"] = profile.requested_retreat_participation
            initial["requested_retreat_group"] = profile.requested_retreat_group_id
            initial["requested_retreat_role"] = (
                profile.requested_retreat_role or "participant"
            )
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = ensure_user_profile(self.request.user)
        ctx["onboarding_status"] = profile.onboarding_status
        ctx["onboarding_note"] = profile.onboarding_note
        if profile.requested_division_id:
            div = profile.requested_division
            region_name = ""
            try:
                region_name = div.region.name if div.region_id else ""
            except Exception:
                region_name = ""
            ctx["requested_division_name"] = (
                f"{region_name} · {div.name}" if region_name else div.name
            )
        else:
            ctx["requested_division_name"] = ""
        ctx["requested_team_name"] = profile.requested_team.name if profile.requested_team_id else ""
        ctx["is_pending_locked"] = bool(
            profile.onboarding_status == UserProfile.OnboardingStatus.PENDING
            and profile.requested_division_id
        )
        ctx["next_url"] = self.request.GET.get("next", "")
        divisions_map = {}
        for d in Division.objects.select_related("region").order_by(
            "region__sort_order", "sort_order", "name"
        ):
            divisions_map.setdefault(str(d.region_id), []).append(
                {"id": d.id, "name": d.name}
            )
        teams_map = {}
        for t in Team.objects.select_related("division").order_by(
            "division__sort_order", "sort_order", "name"
        ):
            teams_map.setdefault(str(t.division_id), []).append({"id": t.id, "name": t.name})
        ctx["divisions_map_json"] = json.dumps(divisions_map, ensure_ascii=False)
        ctx["teams_map_json"] = json.dumps(teams_map, ensure_ascii=False)
        from retreat.models import RetreatEvent, RetreatGroup

        active_retreat = (
            RetreatEvent.objects.filter(is_active=True).order_by("-start_date", "-id").first()
        )
        ctx["active_retreat_event"] = active_retreat
        if active_retreat:
            ctx["retreat_groups_json"] = json.dumps(
                [
                    {
                        "id": g.id,
                        "division_id": g.division_id,
                        "region_id": g.region_id,
                        "label": f"{g.region.name} {g.division.name} {g.name}",
                    }
                    for g in RetreatGroup.objects.filter(event=active_retreat)
                    .select_related("region", "division")
                    .order_by("region__sort_order", "division__sort_order", "order", "id")
                ],
                ensure_ascii=False,
            )
        else:
            ctx["retreat_groups_json"] = "[]"
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

        profile.real_name = (form.cleaned_data["real_name"] or "").strip()
        profile.phone = (form.cleaned_data["phone"] or "").strip()
        profile.requested_division = form.cleaned_data["requested_division"]
        profile.requested_team = form.cleaned_data.get("requested_team")
        profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        profile.onboarding_note = ""
        update_fields = [
            "real_name",
            "phone",
            "requested_division",
            "requested_team",
            "onboarding_status",
            "onboarding_note",
            "updated_at",
        ]
        active_retreat = form.active_retreat_event
        if active_retreat and "requested_retreat_participation" in form.cleaned_data:
            participate = form.cleaned_data["requested_retreat_participation"]
            profile.requested_retreat_participation = participate
            profile.requested_retreat_event = active_retreat if participate else None
            profile.requested_retreat_group = (
                form.cleaned_data.get("requested_retreat_group")
                if participate
                else None
            )
            profile.requested_retreat_role = (
                form.cleaned_data.get("requested_retreat_role") or "participant"
                if participate
                else ""
            )
            update_fields.extend(
                [
                    "requested_retreat_participation",
                    "requested_retreat_event",
                    "requested_retreat_group",
                    "requested_retreat_role",
                ]
            )
        else:
            profile.requested_retreat_participation = False
            profile.requested_retreat_event = None
            profile.requested_retreat_group = None
            profile.requested_retreat_role = ""
            update_fields.extend(
                [
                    "requested_retreat_participation",
                    "requested_retreat_event",
                    "requested_retreat_group",
                    "requested_retreat_role",
                ]
            )
        profile.save(update_fields=update_fields)
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
        if not can_access_onboarding_approvals(request.user):
            raise PermissionDenied("가입 승인 페이지 권한이 없습니다.")
        if not onboarding_approval_divisions_for(request.user).exists():
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
        return set(
            onboarding_approval_divisions_for(self.request.user).values_list("pk", flat=True)
        )

    def _apply_retreat_fields_from_post(self, request, profile: UserProfile) -> None:
        """승인 화면에서 수련회 조·역할 필드 반영."""
        retreat_role = (request.POST.get("retreat_role") or "").strip()
        group_id = (request.POST.get("retreat_group_id") or "").strip()
        update_fields = []
        if retreat_role in ("leader", "vice_leader", "participant", ""):
            profile.requested_retreat_role = retreat_role
            update_fields.append("requested_retreat_role")
        if group_id.isdigit():
            from retreat.models import RetreatGroup

            g = RetreatGroup.objects.filter(pk=int(group_id)).first()
            if g and profile.requested_division_id == g.division_id:
                profile.requested_retreat_group = g
                update_fields.append("requested_retreat_group")
        if update_fields:
            update_fields.append("updated_at")
            profile.save(update_fields=update_fields)

    def _resolve_active_division(self):
        divisions = onboarding_approval_divisions_for(self.request.user).order_by(
            "sort_order", "name"
        )
        if not divisions.exists():
            return None, divisions

        role_code = getattr(getattr(self.request.user, "role_level", None), "code", "")
        requested_code = (self.request.GET.get("division_code") or self.request.POST.get("division_code") or "").strip()
        if (
            role_code in ("pastor", "evangelist")
            or self.request.user.is_superuser
            or divisions.count() > 1
        ):
            active = divisions.filter(code=requested_code).first() if requested_code else None
            if active is None:
                active = prefer_own_division(self.request.user, divisions)
            return active, divisions

        return prefer_own_division(self.request.user, divisions), divisions

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

        self._apply_retreat_fields_from_post(request, profile)

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
            if team is not None and team.division_id != profile.requested_division_id:
                messages.error(request, "신청 팀은 신청 부서에 속해야 합니다.")
                return HttpResponseRedirect(next_url)
            UserDivisionTeam.objects.update_or_create(
                user=profile.user,
                division=profile.requested_division,
                defaults={"team": team, "is_primary": True, "sort_order": 0},
            )
            profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
            profile.onboarding_note = note
            profile.save(update_fields=["onboarding_status", "onboarding_note", "updated_at"])
            from retreat.services.onboarding import apply_retreat_membership_on_approval

            apply_retreat_membership_on_approval(
                user=profile.user,
                profile=profile,
                retreat_group_id=request.POST.get("retreat_group_id"),
                retreat_role=request.POST.get("retreat_role"),
                changed_by=request.user,
            )
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
        ctx["can_choose_onboarding_division"] = allowed_divisions.count() > 1
        ctx["retreat_role_choices"] = [
            ("participant", "참가자"),
            ("leader", "조장"),
            ("vice_leader", "부조장"),
        ]
        ctx["allowed_divisions"] = list(
            allowed_divisions.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )
        ctx["active_division"] = active_division
        ctx["date_from"] = date_from
        ctx["date_to"] = date_to
        ctx["onboarding_status_choices"] = [
            (UserProfile.OnboardingStatus.PENDING, "승인 대기"),
            (UserProfile.OnboardingStatus.APPROVED, "승인 완료"),
            (UserProfile.OnboardingStatus.REJECTED, "반려"),
        ]

        from retreat.models import RetreatEvent, RetreatGroup

        active_retreat = (
            RetreatEvent.objects.filter(is_active=True).order_by("-start_date", "-id").first()
        )
        ctx["active_retreat_event"] = active_retreat
        if active_retreat:
            retreat_groups = list(
                RetreatGroup.objects.filter(event=active_retreat)
                .select_related("region", "division")
                .order_by("region__sort_order", "division__sort_order", "order", "id")
            )
            ctx["retreat_groups"] = retreat_groups
            import json as _json

            ctx["retreat_groups_json"] = _json.dumps(
                [
                    {
                        "id": g.id,
                        "division_id": g.division_id,
                        "region_id": g.region_id,
                        "label": f"{g.region.name} {g.division.name} {g.name}",
                    }
                    for g in retreat_groups
                ],
                ensure_ascii=False,
            )
        else:
            ctx["retreat_groups"] = []
            ctx["retreat_groups_json"] = "[]"

        scoped = (
            UserProfile.objects.select_related(
                "user",
                "requested_division",
                "requested_division__region",
                "requested_team",
                "requested_retreat_event",
                "requested_retreat_group",
            )
            .exclude(user__is_staff=True)
            .exclude(user__is_superuser=True)
            .filter(user__isnull=False, user__is_active=True)
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
        real_name_map = {}
        if user_ids:
            for u in User.objects.filter(pk__in=user_ids).select_related("profile"):
                label_map[u.id] = user_display_name(u, kakao_map=kakao_map)
                prof = getattr(u, "profile", None)
                real_name_map[u.id] = (getattr(prof, "real_name", "") or "").strip()

        ctx["pending_profiles"] = pending_profiles
        ctx["rejected_profiles"] = rejected_profiles
        ctx["approved_profiles"] = approved_profiles
        ctx["user_label_map"] = label_map
        ctx["user_real_name_map"] = real_name_map

        status_label = {code: label for code, label in ctx["onboarding_status_choices"]}
        role_label = {code: label for code, label in ctx["retreat_role_choices"]}

        def _fmt_dt(value):
            if not value:
                return ""
            return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")

        def _profile_label(p):
            # 연결 계정이 있으면 계정 표시명, 없으면 프로필 자체 필드로 폴백.
            if p.user_id and label_map.get(p.user_id):
                return label_map[p.user_id]
            return (
                (p.display_name or "").strip()
                or (p.real_name or "").strip()
                or "(계정 미연결)"
            )

        profile_label_map = {}
        profile_real_name_map = {}
        detail_map = {}
        for p in list(pending_profiles) + list(approved_profiles) + list(rejected_profiles):
            label = _profile_label(p)
            real_name = (p.real_name or "").strip()
            # 셀에는 실명을 우선 표시하고, 없으면 표시명/계정명으로 폴백한다.
            profile_label_map[p.id] = real_name or label
            profile_real_name_map[p.id] = real_name
            div = p.requested_division
            region_name = ""
            if div and div.region_id:
                try:
                    region_name = div.region.name
                except Exception:
                    region_name = ""
            detail_map[p.id] = {
                "label": label,
                "real_name": real_name,
                "phone": (p.phone or "").strip(),
                "kakao_account": (getattr(p.user, "username", "") or "").strip(),
                "kakao_nickname": kakao_map.get(p.user_id, ""),
                "linked_account": bool(p.user_id),
                "region": region_name,
                "division": div.name if div else "",
                "team": p.requested_team.name if p.requested_team_id else "",
                "status": status_label.get(p.onboarding_status, p.onboarding_status),
                "note": (p.onboarding_note or "").strip(),
                "retreat_participation": bool(p.requested_retreat_participation),
                "retreat_event": p.requested_retreat_event.name if p.requested_retreat_event_id else "",
                "retreat_group": p.requested_retreat_group.name if p.requested_retreat_group_id else "",
                "retreat_role": role_label.get(
                    p.requested_retreat_role, p.requested_retreat_role or ""
                ),
                "date_joined": _fmt_dt(getattr(p.user, "date_joined", None)),
                "updated_at": _fmt_dt(p.updated_at),
            }
        ctx["user_detail_json"] = json.dumps(detail_map, ensure_ascii=False)
        ctx["profile_label_map"] = profile_label_map
        ctx["profile_real_name_map"] = profile_real_name_map

        ctx["account_tab"] = "approvals"
        ctx["division_choices"] = list(
            allowed_divisions.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )
        from users.models import Region

        ctx["region_choices"] = list(
            Region.objects.filter(
                pk__in=allowed_divisions.values_list("region_id", flat=True).distinct()
            ).order_by("sort_order", "name")
        )
        team_map = {}
        for t in Team.objects.select_related("division").order_by("division__sort_order", "sort_order", "name"):
            team_map.setdefault(str(t.division_id), []).append({"id": t.id, "name": t.name})
        ctx["teams_map_json"] = json.dumps(team_map, ensure_ascii=False)
        return ctx


class DivisionAccountRoleManageView(LoginRequiredMixin, TemplateView):
    """목사/전도사/관리자용 부서 계정 직책 관리."""

    template_name = "users/division_account_roles.html"
    login_url = reverse_lazy("user_login")

    def _manageable_divisions(self):
        if self.request.user.is_superuser:
            return Division.objects.all().order_by(
                "region__sort_order", "sort_order", "name"
            )
        return membership_divisions_for(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        if not can_manage_division_accounts(request.user):
            raise PermissionDenied("계정 직책 관리 페이지 권한이 없습니다.")
        if not self._manageable_divisions().exists():
            raise PermissionDenied("담당 부서가 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def _resolve_active_division(self):
        divisions = self._manageable_divisions()
        if not divisions.exists():
            return None, divisions

        requested_code = (self.request.GET.get("division_code") or "").strip()
        active = divisions.filter(code=requested_code).first() if requested_code else None
        if active is None:
            active = prefer_own_division(self.request.user, divisions)
        return active, divisions

    def _division_functional_department(self, division: Division):
        return FunctionalDepartment.objects.get_or_create(
            code=f"division_{division.code}",
            defaults={"name": f"{division.name} 운영", "division": division, "sort_order": 0},
        )[0]

    def _roles_redirect(self, division: Division | None) -> str:
        base = reverse_lazy("user_division_account_roles")
        if division is None:
            return str(base)
        return f"{base}?division_code={division.code}"

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        active_division, _ = self._resolve_active_division()
        if active_division is None:
            messages.error(request, "관리 가능한 부서가 없습니다.")
            return HttpResponseRedirect(reverse_lazy("user_division_account_roles"))

        redirect_url = self._roles_redirect(active_division)
        user_id = (request.POST.get("user_id") or "").strip()
        team_id = (request.POST.get("team_id") or "").strip()
        division_id_raw = (request.POST.get("division_id") or "").strip()
        valid_role_codes = set(Role.objects.values_list("code", flat=True))
        selected_role_codes = [c for c in request.POST.getlist("role_codes") if c in valid_role_codes]
        manage_attendance = request.POST.get("can_manage_attendance") == "on"
        manage_parking = request.POST.get("can_manage_parking") == "on"
        manage_accounts = request.POST.get("can_manage_accounts") == "on"
        real_name = (request.POST.get("real_name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        retreat_group_id = (request.POST.get("retreat_group_id") or "").strip()
        retreat_role = (request.POST.get("retreat_role") or "").strip()

        if not user_id.isdigit():
            messages.error(request, "대상 사용자를 선택해 주세요.")
            return HttpResponseRedirect(redirect_url)

        target_user = User.objects.filter(pk=int(user_id), is_active=True).first()
        if target_user is None:
            messages.error(request, "대상 사용자를 찾을 수 없습니다.")
            return HttpResponseRedirect(redirect_url)
        if not target_user.division_teams.filter(division=active_division).exists():
            messages.error(request, "선택한 부서 소속 계정만 수정할 수 있습니다.")
            return HttpResponseRedirect(redirect_url)

        target_division = active_division
        if request.user.is_superuser and division_id_raw.isdigit():
            new_division = Division.objects.filter(pk=int(division_id_raw)).first()
            if new_division is None:
                messages.error(request, "선택한 부서를 찾을 수 없습니다.")
                return HttpResponseRedirect(redirect_url)
            target_division = new_division
        elif division_id_raw.isdigit() and int(division_id_raw) != active_division.id:
            messages.error(request, "부서 이동은 슈퍼유저만 가능합니다.")
            return HttpResponseRedirect(redirect_url)

        selected_team = None
        if team_id:
            if not team_id.isdigit():
                messages.error(request, "팀 선택 값이 올바르지 않습니다.")
                return HttpResponseRedirect(redirect_url)
            selected_team = Team.objects.filter(
                pk=int(team_id), division=target_division
            ).first()
            if selected_team is None:
                messages.error(request, "선택한 팀을 찾을 수 없습니다.")
                return HttpResponseRedirect(redirect_url)

        user_updates = []
        if target_user.can_manage_attendance != manage_attendance:
            target_user.can_manage_attendance = manage_attendance
            user_updates.append("can_manage_attendance")
        if target_user.can_manage_parking != manage_parking:
            target_user.can_manage_parking = manage_parking
            user_updates.append("can_manage_parking")
        if target_user.can_manage_accounts != manage_accounts:
            target_user.can_manage_accounts = manage_accounts
            user_updates.append("can_manage_accounts")
        if user_updates:
            target_user.save(update_fields=user_updates)

        old_membership = (
            target_user.division_teams.filter(division=active_division)
            .order_by("-is_primary", "sort_order", "id")
            .first()
        )
        if target_division.id != active_division.id:
            target_membership = target_user.division_teams.filter(
                division=target_division
            ).first()
            if target_membership:
                target_membership.team = selected_team
                target_membership.is_primary = True
                target_membership.save(update_fields=["team", "is_primary"])
                if old_membership and old_membership.pk != target_membership.pk:
                    old_membership.delete()
            elif old_membership:
                old_membership.division = target_division
                old_membership.team = selected_team
                old_membership.save(update_fields=["division", "team"])
            else:
                UserDivisionTeam.objects.create(
                    user=target_user,
                    division=target_division,
                    team=selected_team,
                    is_primary=True,
                    sort_order=0,
                )
        elif old_membership:
            if old_membership.team_id != (selected_team.id if selected_team else None):
                old_membership.team = selected_team
                old_membership.save(update_fields=["team"])
        else:
            UserDivisionTeam.objects.create(
                user=target_user,
                division=target_division,
                team=selected_team,
                is_primary=True,
                sort_order=0,
            )

        profile = ensure_user_profile(target_user)
        prof_updates = []
        if real_name:
            profile.real_name = real_name
            prof_updates.append("real_name")
        if phone:
            try:
                validate_korea_mobile_phone(phone)
                profile.phone = phone
                prof_updates.append("phone")
            except Exception:
                messages.error(request, "휴대폰 번호 형식이 올바르지 않습니다.")
                return HttpResponseRedirect(redirect_url)

        profile.requested_division = target_division
        profile.requested_team = selected_team
        prof_updates.extend(["requested_division", "requested_team"])

        from retreat.models import RetreatEvent

        active_retreat = (
            RetreatEvent.objects.filter(is_active=True)
            .order_by("-start_date", "-id")
            .first()
        )
        if active_retreat:
            if retreat_group_id.isdigit():
                group = RetreatGroup.objects.filter(
                    pk=int(retreat_group_id),
                    division=target_division,
                    event=active_retreat,
                ).first()
                if group is None:
                    messages.error(request, "선택한 수련회 조를 찾을 수 없습니다.")
                    return HttpResponseRedirect(redirect_url)
                profile.requested_retreat_participation = True
                profile.requested_retreat_event = active_retreat
                profile.requested_retreat_group = group
                prof_updates.extend(
                    [
                        "requested_retreat_participation",
                        "requested_retreat_event",
                        "requested_retreat_group",
                    ]
                )
            else:
                profile.requested_retreat_participation = False
                profile.requested_retreat_event = None
                profile.requested_retreat_group = None
                prof_updates.extend(
                    [
                        "requested_retreat_participation",
                        "requested_retreat_event",
                        "requested_retreat_group",
                    ]
                )
            if retreat_role in ("leader", "vice_leader", "participant", ""):
                profile.requested_retreat_role = retreat_role
                prof_updates.append("requested_retreat_role")

        if prof_updates:
            prof_updates.append("updated_at")
            profile.save(update_fields=list(dict.fromkeys(prof_updates)))

        if active_retreat and profile.requested_retreat_participation:
            from retreat.services.onboarding import apply_retreat_membership_on_approval

            apply_retreat_membership_on_approval(
                user=target_user,
                profile=profile,
                retreat_group_id=str(profile.requested_retreat_group_id or ""),
                retreat_role=profile.requested_retreat_role,
                changed_by=request.user,
            )

        if target_division.id != active_division.id:
            old_department = self._division_functional_department(active_division)
            UserFunctionalDeptRole.objects.filter(
                user=target_user, functional_department=old_department
            ).delete()

        department = self._division_functional_department(target_division)
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

        if target_division.id != active_division.id:
            messages.success(
                request,
                f"{user_display_name(target_user)} 계정을 {target_division.name}(으)로 이동했습니다.",
            )
        else:
            messages.success(
                request, f"{user_display_name(target_user)} 계정 정보를 저장했습니다."
            )
        return HttpResponseRedirect(redirect_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        active_division, allowed_divisions = self._resolve_active_division()
        can_choose_division = (
            self.request.user.is_superuser or allowed_divisions.count() > 1
        )

        from retreat.models import RetreatEvent, RetreatGroupMembership

        active_retreat = (
            RetreatEvent.objects.filter(is_active=True)
            .order_by("-start_date", "-id")
            .first()
        )
        retreat_groups_json = "[]"
        if active_retreat:
            retreat_groups = list(
                RetreatGroup.objects.filter(event=active_retreat)
                .select_related("region", "division")
                .order_by(
                    "region__sort_order",
                    "division__sort_order",
                    "order",
                    "id",
                )
            )
            retreat_groups_json = json.dumps(
                [
                    {
                        "id": g.id,
                        "division_id": g.division_id,
                        "region_id": g.region_id,
                        "label": f"{g.region.name} {g.division.name} {g.name}",
                    }
                    for g in retreat_groups
                ],
                ensure_ascii=False,
            )

        division_choices = list(
            allowed_divisions.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )
        if self.request.user.is_superuser:
            division_choices = list(
                Division.objects.select_related("region").order_by(
                    "region__sort_order", "sort_order", "name"
                )
            )

        team_map: dict[str, list] = {}
        for team in Team.objects.select_related("division").order_by(
            "division__sort_order", "sort_order", "name"
        ):
            team_map.setdefault(str(team.division_id), []).append(
                {"id": team.id, "name": team.name}
            )

        membership_map: dict[int, int | None] = {}
        users_payload = []
        if active_division:
            department = self._division_functional_department(active_division)
            user_qs = (
                User.objects.filter(division_teams__division=active_division, is_active=True)
                .select_related("role_level", "profile")
                .distinct()
                .order_by("username")
            )
            for row in (
                UserDivisionTeam.objects.filter(
                    user__in=user_qs, division=active_division
                )
                .order_by("-is_primary", "sort_order", "id")
                .values("user_id", "team_id")
            ):
                if row["user_id"] in membership_map:
                    continue
                membership_map[row["user_id"]] = row["team_id"]

            retreat_membership_map: dict[int, tuple[int | None, str]] = {}
            if active_retreat:
                for mem in RetreatGroupMembership.objects.filter(
                    user__in=user_qs, group__event=active_retreat
                ).select_related("group"):
                    retreat_membership_map[mem.user_id] = (mem.group_id, mem.role)

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
                prof = getattr(u, "profile", None)
                region_id = active_division.region_id if active_division else None
                region_name = active_division.region.name if region_id else ""
                team_id = membership_map.get(u.id)
                retreat_group_id = None
                retreat_role = ""
                if active_retreat and prof:
                    if (
                        prof.requested_retreat_group_id
                        and prof.requested_retreat_event_id == active_retreat.id
                    ):
                        retreat_group_id = prof.requested_retreat_group_id
                        retreat_role = prof.requested_retreat_role or "participant"
                    elif u.id in retreat_membership_map:
                        retreat_group_id, retreat_role = retreat_membership_map[u.id]
                        retreat_role = retreat_role or "participant"

                users_payload.append(
                    {
                        "id": u.id,
                        "username": u.username,
                        "real_name": (getattr(prof, "real_name", "") or "").strip(),
                        "phone": getattr(prof, "phone", "") or "",
                        "region_id": region_id,
                        "region_name": region_name,
                        "division_id": active_division.id if active_division else None,
                        "division_name": active_division.name if active_division else "",
                        "team_id": team_id,
                        "retreat_group_id": retreat_group_id,
                        "retreat_role": retreat_role,
                        "assigned_role_codes": sorted(list(role_map.get(u.id, set()))),
                        "assigned_role_codes_json": json.dumps(
                            sorted(list(role_map.get(u.id, set()))),
                            ensure_ascii=False,
                        ),
                        "can_manage_attendance": bool(
                            getattr(u, "can_manage_attendance", False)
                        ),
                        "can_manage_parking": bool(
                            getattr(u, "can_manage_parking", False)
                        ),
                        "can_manage_accounts": bool(
                            getattr(u, "can_manage_accounts", False)
                        ),
                    }
                )

        region_qs = Region.objects.all().order_by("sort_order", "name")
        if not self.request.user.is_superuser and active_division and active_division.region_id:
            region_qs = Region.objects.filter(pk=active_division.region_id)

        ctx["allowed_divisions"] = division_choices
        ctx["active_division"] = active_division
        ctx["can_choose_division"] = can_choose_division
        ctx["can_move_division"] = self.request.user.is_superuser
        ctx["users_payload"] = users_payload
        ctx["region_choices"] = list(region_qs)
        ctx["divisions_json"] = json.dumps(
            [
                {
                    "id": d.id,
                    "region_id": d.region_id,
                    "name": d.name,
                    "region_name": d.region.name if d.region_id else "",
                }
                for d in division_choices
            ],
            ensure_ascii=False,
        )
        ctx["teams_map_json"] = json.dumps(team_map, ensure_ascii=False)
        ctx["active_retreat_event"] = active_retreat
        ctx["retreat_groups_json"] = retreat_groups_json
        ctx["retreat_role_choices"] = [
            ("participant", "참가자"),
            ("leader", "조장"),
            ("vice_leader", "부조장"),
        ]
        ctx["account_tab"] = "roles"
        ctx["role_options_api_url"] = reverse_lazy("api_user_assignable_roles")
        return ctx


class AssignableRoleOptionsApiView(LoginRequiredMixin, TemplateView):
    """직책(Role) 전체 목록. 출석/주차 등 권한 연동용 코드는 없을 때 자동 생성."""

    _bootstrap_role_codes = (
        ("dept_head", "부장", 10),
        ("deputy_dept_head", "차장", 11),
        ("secretary", "간사", 12),
        ("instrument_leader", "기악장", 13),
        ("worship_leader", "워십장", 14),
        ("choir_leader", "단장", 15),
        ("vice_choir_leader", "부단장", 16),
        ("leader", "리더", 17),
    )
    login_url = reverse_lazy("user_login")

    def get(self, request, *args, **kwargs):
        if not can_manage_division_accounts(request.user):
            raise PermissionDenied("직책 목록 조회 권한이 없습니다.")
        for code, name_ko, order in self._bootstrap_role_codes:
            Role.objects.get_or_create(code=code, defaults={"name": name_ko, "sort_order": order})
        roles = list(Role.objects.order_by("sort_order", "name").values("code", "name"))
        return JsonResponse({"results": roles})
