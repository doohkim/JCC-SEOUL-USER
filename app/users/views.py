from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import urlencode
from django.db import transaction
from django.db.models import Q
from datetime import datetime, time, timedelta
import json
from django.views.generic import FormView, TemplateView

from users.mixins import ensure_user_profile, is_onboarding_complete
from users.models import (
    Division,
    FunctionalDepartment,
    Region,
    Role,
    RoleLevel,
    Team,
    User,
    UserDivisionTeam,
    UserFunctionalDeptRole,
    UserProfile,
)
from users.permissions import (
    can_access_onboarding_approvals,
    can_manage_division_accounts,
    is_platform_admin,
    membership_divisions_for,
    onboarding_approval_divisions_for,
)
from users.validators import normalize_korea_mobile_phone, validate_korea_mobile_phone
from retreat.models import (
    RetreatAttendee,
    RetreatChangeLog,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
from users.services.user_display import kakao_nickname_map_for_user_ids, user_display_name
from users.services.user_avatar import user_profile_avatar_url


def prefer_own_division(user, divisions):
    """관리 가능 부서 중 본인 대표(우선) 소속 부서를 선택."""
    udt = (
        user.division_teams.filter(division__in=divisions)
        .order_by("-is_primary", "sort_order", "id")
        .select_related("division")
        .first()
    )
    if udt:
        preferred = divisions.filter(pk=udt.division_id).first()
        if preferred is not None:
            return preferred
    return divisions.first()


def primary_membership_division(user, *, within=None):
    """대표(우선) 소속 부서. within 이 있으면 그 범위 안에서만 조회."""
    qs = user.division_teams.select_related("division").order_by(
        "-is_primary", "sort_order", "id"
    )
    if within is not None:
        qs = qs.filter(division__in=within)
    udt = qs.first()
    return udt.division if udt else None


def _kakao_account_display(username: str) -> str:
    raw = (username or "").strip()
    return raw[6:] if raw.startswith("kakao_") else raw


def _onboarding_status_labels() -> dict[str, str]:
    return {
        UserProfile.OnboardingStatus.PENDING: "승인 대기",
        UserProfile.OnboardingStatus.APPROVED: "승인 완료",
        UserProfile.OnboardingStatus.REJECTED: "반려",
    }


def _activity_datetime_label(dt) -> str:
    if not dt:
        return "-"
    return timezone.localtime(dt).strftime("%Y.%m.%d %H:%M")


def _activity_date_label(dt) -> str:
    if not dt:
        return "-"
    return timezone.localtime(dt).strftime("%Y.%m.%d")


def _activity_actor_kind(actor: str, *, self_actor: bool = False) -> str:
    if self_actor:
        return "self"
    s = (actor or "").strip()
    if not s or s == "-" or "시스템" in s:
        return "system"
    return "admin"


def _activity_actor_label(kind: str, actor: str) -> str:
    if kind == "self":
        return "본인 (웹 신청)"
    if kind == "system":
        return "시스템 (자동)"
    s = (actor or "").strip()
    if s and s != "-":
        return f"관리자 {s}"
    return "관리자"


def _activity_category_from_summary(summary: str) -> tuple[str, str]:
    s = summary or ""
    if "승인 상태" in s or "승인" in s or "반려" in s:
        return "승인 상태 변경", "status"
    if any(k in s for k in ("전화", "연락", "휴대", "실명", "이름", "메모", "최종 수정")):
        return "개인 정보 수정", "profile"
    if any(k in s for k in ("조원", "조 ", "운영진", "수련회", "배정")):
        return "조 배정 변경", "group"
    return "기타 변경", "other"


def _activity_parse_change(summary: str) -> dict[str, str | None]:
    s = (summary or "").strip()
    if s.startswith("승인 상태: "):
        after = s.split(":", 1)[1].strip()
        return {"detail": s, "before": None, "after": after}
    if " → " not in s:
        return {"detail": s, "before": None, "after": None}
    before_part, after = s.rsplit(" → ", 1)
    after = after.strip()
    if ": " in before_part:
        label, before_val = before_part.split(": ", 1)
        before_val = before_val.strip()
        return {
            "detail": f"{label}: {before_val} → {after}",
            "before": before_val,
            "after": after,
        }
    return {
        "detail": s,
        "before": before_part.strip(),
        "after": after,
    }


def _activity_item(
    *,
    at_dt,
    actor: str,
    summary: str,
    actor_kind: str | None = None,
    category: str | None = None,
    tone: str | None = None,
) -> dict:
    kind = actor_kind or _activity_actor_kind(actor)
    cat_label, cat_tone = (
        (category, tone)
        if category and tone
        else _activity_category_from_summary(summary)
    )
    change = _activity_parse_change(summary)
    return {
        "at": _activity_datetime_label(at_dt),
        "category": cat_label,
        "tone": cat_tone,
        "actor": _activity_actor_label(kind, actor),
        "actor_kind": kind,
        "detail": change["detail"],
        "before": change["before"],
        "after": change["after"],
        "summary": summary,
    }


def build_onboarding_application_activity_log(profile: UserProfile) -> list[dict]:
    """가입신청서·계정 관리 활동 로그(집계형): 스냅샷 + 수련회 변경 이력."""
    status_labels = _onboarding_status_labels()
    entries: list[tuple[timezone.datetime, str, str, str | None, str | None, str | None]] = []
    user = profile.user if profile.user_id else None

    if user and user.date_joined:
        signup_detail = f"{user.get_signup_source_display()}을 통한 신규 가입 완료"
        entries.append(
            (
                timezone.localtime(user.date_joined),
                "",
                signup_detail,
                "self",
                "신규 등록",
                "signup",
            )
        )

    if profile.updated_at:
        at = timezone.localtime(profile.updated_at)
        status_text = status_labels.get(profile.onboarding_status, profile.onboarding_status)
        entries.append(
            (
                at,
                "-",
                f"승인 상태: {status_text}",
                "system",
                "승인 상태 변경",
                "status",
            )
        )
        note = (profile.onboarding_note or "").strip()
        if note:
            entries.append(
                (
                    at,
                    "-",
                    f"메모: {note}",
                    "system",
                    "개인 정보 수정",
                    "profile",
                )
            )

    if profile.user_id:
        attendee_ids = list(
            RetreatAttendee.objects.filter(user_id=profile.user_id).values_list("id", flat=True)
        )
        membership_ids = list(
            RetreatGroupMembership.objects.filter(user_id=profile.user_id).values_list(
                "id", flat=True
            )
        )
        log_filters = Q()
        if attendee_ids:
            log_filters |= Q(
                target_type=RetreatChangeLog.TargetType.ATTENDEE,
                target_id__in=attendee_ids,
            )
        if membership_ids:
            log_filters |= Q(
                target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
                target_id__in=membership_ids,
            )
        if log_filters:
            from retreat.services.changelog_format import humanize_change_logs

            logs = (
                RetreatChangeLog.objects.filter(log_filters)
                .select_related("changed_by", "changed_by__profile")
                .order_by("-changed_at", "-id")[:30]
            )
            for item in humanize_change_logs(logs):
                at = timezone.localtime(item.log.changed_at)
                category, tone = _activity_category_from_summary(item.summary)
                entries.append((at, item.actor or "-", item.summary, None, category, tone))

    if not entries:
        return []

    entries.sort(key=lambda row: row[0], reverse=True)
    seen: set[tuple[str, str, str]] = set()
    items: list[dict] = []
    for at, actor, summary, actor_kind, category, tone in entries:
        key = (at.strftime("%Y-%m-%d %H:%M"), actor, summary)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            _activity_item(
                at_dt=at,
                actor=actor,
                summary=summary,
                actor_kind=actor_kind,
                category=category,
                tone=tone,
            )
        )
    return items


def _phone_for_display(phone: str) -> str:
    raw = (phone or "").strip()
    if not raw:
        return ""
    normalized = normalize_korea_mobile_phone(raw)
    return normalized if normalized is not None else raw


def _profile_updated_label(updated_at) -> str:
    if not updated_at:
        return ""
    delta = timezone.now() - updated_at
    days = delta.days
    if days <= 0:
        return "오늘 업데이트됨"
    if days == 1:
        return "1일 전 업데이트"
    return f"{days}일 전 업데이트"


class KakaoAuthEntryView(TemplateView):
    template_name = "users/signup.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            profile = ensure_user_profile(request.user)
            if is_onboarding_complete(request.user, profile):
                return HttpResponseRedirect(reverse_lazy("notice_list"))
            return HttpResponseRedirect(reverse_lazy("user_onboarding"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        query = {"next": self.request.GET.get("next", "/onboarding/")}
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
    gender = forms.ChoiceField(
        label="성별",
        choices=UserProfile.Gender.choices,
        widget=forms.Select(attrs={"class": "gender-select"}),
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
    requested_applicant_role = forms.ChoiceField(
        label="직급",
        choices=UserProfile.ApplicantRole.choices,
        initial=UserProfile.ApplicantRole.MEMBER,
        required=False,
        widget=forms.Select(attrs={"class": "applicant-role-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["gender"].empty_label = "성별을 선택해 주세요"

    def clean(self):
        cleaned = super().clean()
        region = cleaned.get("requested_region")
        division = cleaned.get("requested_division")
        team = cleaned.get("requested_team")
        applicant_role = (
            cleaned.get("requested_applicant_role") or UserProfile.ApplicantRole.MEMBER
        )
        cleaned["requested_applicant_role"] = applicant_role
        is_pastoral_applicant_role = applicant_role in (
            UserProfile.ApplicantRole.PASTOR,
            UserProfile.ApplicantRole.EVANGELIST,
        )

        if division and region and division.region_id != region.id:
            self.add_error("requested_division", "선택한 부서는 해당 지역에 속해야 합니다.")
        if team and division and team.division_id != division.id:
            self.add_error("requested_team", "선택한 팀은 해당 부서에 속하지 않습니다.")

        if is_pastoral_applicant_role:
            cleaned["requested_team"] = None
        cleaned["retreat_participation"] = False
        return cleaned


class UserOnboardingView(LoginRequiredMixin, FormView):
    template_name = "users/onboarding.html"
    form_class = OnboardingRequestForm
    login_url = reverse_lazy("user_login")
    success_url = reverse_lazy("user_onboarding")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        profile = ensure_user_profile(request.user)
        if is_onboarding_complete(request.user, profile):
            target = request.GET.get("next") or "/notices/"
            return HttpResponseRedirect(target)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        profile = ensure_user_profile(self.request.user)
        initial = {
            "real_name": profile.real_name or "",
            "phone": profile.phone or "",
            "gender": profile.gender or "",
            "requested_division": profile.requested_division_id,
            "requested_team": profile.requested_team_id,
            "requested_applicant_role": profile.requested_applicant_role
            or UserProfile.ApplicantRole.MEMBER,
        }
        if profile.requested_division_id:
            try:
                initial["requested_region"] = profile.requested_division.region_id
            except Exception:
                pass
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
        ctx["requested_applicant_role"] = profile.requested_applicant_role or UserProfile.ApplicantRole.MEMBER
        ctx["requested_applicant_role_label"] = dict(UserProfile.ApplicantRole.choices).get(
            ctx["requested_applicant_role"], "성도"
        )
        ctx["requested_gender_label"] = dict(UserProfile.Gender.choices).get(
            profile.gender, ""
        )
        ctx["is_pastoral_applicant"] = ctx["requested_applicant_role"] in (
            UserProfile.ApplicantRole.PASTOR,
            UserProfile.ApplicantRole.EVANGELIST,
        )
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
        return ctx

    def form_valid(self, form):
        profile = ensure_user_profile(self.request.user)
        if profile.onboarding_status == UserProfile.OnboardingStatus.APPROVED:
            messages.info(self.request, "이미 승인된 계정입니다. 화면이 자동 갱신됩니다.")
            return HttpResponseRedirect(reverse_lazy("notice_list"))
        if (
            profile.onboarding_status == UserProfile.OnboardingStatus.PENDING
            and profile.requested_division_id
        ):
            messages.info(self.request, "이미 신청이 접수되어 승인 대기 중입니다.")
            return HttpResponseRedirect(self.get_success_url())

        profile.real_name = (form.cleaned_data["real_name"] or "").strip()
        profile.phone = (form.cleaned_data["phone"] or "").strip()
        profile.gender = form.cleaned_data.get("gender") or ""
        profile.requested_division = form.cleaned_data["requested_division"]
        is_pastoral = form.cleaned_data.get(
            "requested_applicant_role", UserProfile.ApplicantRole.MEMBER
        ) in (
            UserProfile.ApplicantRole.PASTOR,
            UserProfile.ApplicantRole.EVANGELIST,
        )
        profile.requested_team = None if is_pastoral else form.cleaned_data.get("requested_team")
        profile.requested_applicant_role = form.cleaned_data.get(
            "requested_applicant_role", UserProfile.ApplicantRole.MEMBER
        )
        profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        profile.onboarding_note = ""
        profile.requested_retreat_participation = False
        profile.requested_retreat_event = None
        profile.requested_retreat_group = None
        profile.requested_retreat_role = ""
        update_fields = [
            "real_name",
            "phone",
            "gender",
            "requested_division",
            "requested_team",
            "requested_applicant_role",
            "onboarding_status",
            "onboarding_note",
            "requested_retreat_participation",
            "requested_retreat_event",
            "requested_retreat_group",
            "requested_retreat_role",
            "updated_at",
        ]
        profile.save(update_fields=update_fields)
        messages.success(self.request, "소속 신청이 접수되었습니다. 관리자 승인 후 이용 가능합니다.")
        return super().form_valid(form)


class UserLogoutView(TemplateView):
    """운영 사용자 로그아웃 엔드포인트."""

    def get(self, request, *args, **kwargs):
        logout(request)
        return HttpResponseRedirect(reverse_lazy("user_login"))


INTEREST_TOPICS_MAX_LEN = 500
INTEREST_TOPIC_MAX_TAGS = 15
INTEREST_TOPIC_MAX_TAG_LEN = 30


def _normalize_interest_topics(raw: str) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for chunk in (raw or "").split(","):
        tag = chunk.strip().lstrip("#").strip()
        if not tag or len(tag) > INTEREST_TOPIC_MAX_TAG_LEN:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        parts.append(tag)
        if len(parts) >= INTEREST_TOPIC_MAX_TAGS:
            break
    return ",".join(parts)[:INTEREST_TOPICS_MAX_LEN]


class UserProfileForm(forms.Form):
    real_name = forms.CharField(label="실명", max_length=50)
    phone = forms.CharField(
        label="휴대폰",
        max_length=30,
        validators=[validate_korea_mobile_phone],
    )
    bio = forms.CharField(
        label="소개",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 4, "placeholder": "자신을 소개해주세요."},
        ),
    )
    avatar = forms.ImageField(label="프로필 이미지", required=False)
    interest_topics = forms.CharField(
        label="관심 주제",
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean_interest_topics(self):
        return _normalize_interest_topics(self.cleaned_data.get("interest_topics") or "")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("real_name", "phone"):
            self.fields[name].widget.attrs.setdefault("class", "jcc-profileInput")
        self.fields["bio"].widget.attrs.setdefault("class", "jcc-profileTextarea")
        self.fields["avatar"].widget.attrs.update(
            {
                "class": "jcc-profileAvatarInput",
                "accept": "image/jpeg,image/png,image/webp",
            }
        )


class UserProfileView(LoginRequiredMixin, FormView):
    """본인 프로필 조회·일부 수정."""

    template_name = "users/profile.html"
    form_class = UserProfileForm
    login_url = reverse_lazy("user_login")
    success_url = reverse_lazy("user_profile")

    def get_initial(self):
        profile = ensure_user_profile(self.request.user)
        return {
            "real_name": profile.real_name or "",
            "phone": profile.phone or "",
            "bio": profile.bio or "",
            "interest_topics": profile.interest_topics or "",
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        profile = ensure_user_profile(user)
        ctx["profile"] = profile
        ctx["display_label"] = user_display_name(user)
        ctx["memberships"] = list(
            user.division_teams.select_related("division", "division__region", "team")
            .order_by("-is_primary", "sort_order", "division__sort_order", "division__name")
        )
        ctx["onboarding_complete"] = is_onboarding_complete(user, profile)
        ctx["onboarding_status_label"] = profile.get_onboarding_status_display()
        ctx["onboarding_status"] = profile.onboarding_status
        rl = getattr(user, "role_level", None)
        ctx["role_level_name"] = getattr(rl, "name", "") if rl else ""
        ctx["profile_updated_label"] = _profile_updated_label(profile.updated_at)
        return ctx

    def form_valid(self, form):
        profile = ensure_user_profile(self.request.user)
        profile.real_name = (form.cleaned_data["real_name"] or "").strip()
        phone_raw = (form.cleaned_data["phone"] or "").strip()
        normalized = normalize_korea_mobile_phone(phone_raw)
        profile.phone = normalized if normalized is not None else phone_raw
        profile.bio = (form.cleaned_data.get("bio") or "").strip()
        profile.interest_topics = form.cleaned_data.get("interest_topics") or ""
        avatar = form.cleaned_data.get("avatar")
        if avatar:
            profile.avatar = avatar
            profile.avatar_user_uploaded = True
        profile.save()
        messages.success(self.request, "프로필을 저장했습니다.")
        return super().form_valid(form)


class OnboardingApplicationsListView(LoginRequiredMixin, TemplateView):
    """목사/전도사/관리자용 가입신청서 조회·승인 페이지."""

    template_name = "users/onboarding_applications.html"
    login_url = reverse_lazy("user_login")
    ALL_DIVISIONS_CODE = "__all__"

    def dispatch(self, request, *args, **kwargs):
        if not can_access_onboarding_approvals(request.user):
            raise PermissionDenied("가입신청서 페이지 권한이 없습니다.")
        if not onboarding_approval_divisions_for(request.user).exists():
            raise PermissionDenied("담당 부서가 없어 가입신청서를 이용할 수 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    _page_size = 20

    def _applications_query_base(self) -> str:
        q = {}
        for key in ("date_from", "date_to", "division_code", "q", "region_id", "status"):
            v = (self.request.GET.get(key) or "").strip()
            if v:
                q[key] = v
        return urlencode(q)

    def _applications_list_redirect(self, request) -> str:
        q = {}
        for key in ("date_from", "date_to", "division_code", "q", "region_id", "status", "page"):
            v = (request.POST.get(key) or request.GET.get(key) or "").strip()
            if v:
                q[key] = v
        list_status = (request.POST.get("list_status") or "").strip()
        if list_status and "status" not in q:
            q["status"] = list_status
        base = reverse("user_onboarding_applications")
        return f"{base}?{urlencode(q)}" if q else base

    def _allowed_division_ids(self) -> set[int]:
        return set(
            onboarding_approval_divisions_for(self.request.user).values_list("pk", flat=True)
        )

    def _resolve_active_division(self):
        divisions = onboarding_approval_divisions_for(self.request.user).order_by(
            "region__sort_order", "sort_order", "name"
        )
        if not divisions.exists():
            return None, divisions

        requested_code = (
            self.request.GET.get("division_code") or self.request.POST.get("division_code") or ""
        ).strip()

        if requested_code == self.ALL_DIVISIONS_CODE:
            if is_platform_admin(self.request.user) or divisions.count() > 1:
                return None, divisions
            requested_code = ""

        if requested_code:
            active = divisions.filter(code=requested_code).first()
            if active is not None:
                return active, divisions

        primary = primary_membership_division(self.request.user, within=divisions)
        if primary is not None:
            return primary, divisions

        if divisions.count() == 1:
            return divisions.first(), divisions

        if is_platform_admin(self.request.user):
            return None, divisions

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

    def _post_update_profile(self, request, profile, allowed_ids, next_url):
        if profile.requested_division_id and profile.requested_division_id not in allowed_ids:
            messages.error(request, "담당 부서 신청 건만 수정할 수 있습니다.")
            return HttpResponseRedirect(next_url)

        division_id_raw = (request.POST.get("requested_division_id") or "").strip()
        if not division_id_raw.isdigit():
            messages.error(request, "부서를 선택해 주세요.")
            return HttpResponseRedirect(next_url)

        division = Division.objects.filter(pk=int(division_id_raw)).first()
        if division is None:
            messages.error(request, "선택한 부서를 찾을 수 없습니다.")
            return HttpResponseRedirect(next_url)
        if division.id not in allowed_ids:
            messages.error(request, "담당 부서가 아닌 소속은 지정할 수 없습니다.")
            return HttpResponseRedirect(next_url)

        team_id_raw = (request.POST.get("requested_team_id") or "").strip()
        team = None
        if team_id_raw.isdigit():
            team = Team.objects.filter(pk=int(team_id_raw), division=division).first()
            if team is None:
                messages.error(request, "선택한 팀은 해당 부서에 속해야 합니다.")
                return HttpResponseRedirect(next_url)

        phone_raw = (request.POST.get("phone") or "").strip()
        if phone_raw:
            try:
                validate_korea_mobile_phone(phone_raw)
            except ValidationError:
                messages.error(request, "휴대폰 번호 형식이 올바르지 않습니다.")
                return HttpResponseRedirect(next_url)
        normalized = normalize_korea_mobile_phone(phone_raw)
        phone = normalized if normalized is not None else phone_raw

        retreat_event_id_raw = (request.POST.get("requested_retreat_event_id") or "").strip()
        retreat_group_id_raw = (request.POST.get("requested_retreat_group_id") or "").strip()

        from retreat.services.onboarding import resolve_requested_retreat_assignment

        retreat_err = resolve_requested_retreat_assignment(
            profile,
            division=division,
            event_id_raw=retreat_event_id_raw,
            group_id_raw=retreat_group_id_raw,
        )
        if retreat_err:
            messages.error(request, retreat_err)
            return HttpResponseRedirect(next_url)

        profile.real_name = (request.POST.get("real_name") or "").strip()
        profile.display_name = (request.POST.get("display_name") or "").strip()
        profile.phone = phone
        profile.requested_division = division
        profile.requested_team = team
        profile.save(
            update_fields=[
                "real_name",
                "display_name",
                "phone",
                "requested_division",
                "requested_team",
                "requested_retreat_participation",
                "requested_retreat_event",
                "requested_retreat_group",
                "requested_retreat_role",
                "updated_at",
            ]
        )
        label = profile.real_name or user_display_name(profile.user) if profile.user_id else "신청자"
        messages.success(request, f"{label} 가입신청서 정보를 저장했습니다.")
        if profile.onboarding_status == UserProfile.OnboardingStatus.APPROVED:
            from retreat.services.onboarding import sync_retreat_attendee_from_onboarding_profile

            sync_retreat_attendee_from_onboarding_profile(
                user=profile.user,
                profile=profile,
                changed_by=request.user,
            )
        return HttpResponseRedirect(next_url)

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "").strip()
        profile_id = request.POST.get("profile_id", "").strip()
        next_url = self._applications_list_redirect(request)
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

        if action == "update_profile":
            return self._post_update_profile(request, profile, allowed_ids, next_url)

        posted_status = (request.POST.get("onboarding_status") or "").strip()
        if action == "save":
            if posted_status == UserProfile.OnboardingStatus.APPROVED:
                action = "approve"
            elif posted_status == UserProfile.OnboardingStatus.REJECTED:
                action = "reject"

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
            messages.error(
                request,
                "승인 상태를 선택해 주세요."
                if action == "save" and not selected_status
                else "상태 선택 값이 올바르지 않습니다.",
            )
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

            from retreat.services.onboarding import (
                resolve_requested_retreat_assignment,
                sync_retreat_attendee_from_onboarding_profile,
            )

            retreat_err = resolve_requested_retreat_assignment(
                profile,
                division=profile.requested_division,
                event_id_raw=(request.POST.get("requested_retreat_event_id") or "").strip(),
                group_id_raw=(request.POST.get("requested_retreat_group_id") or "").strip(),
            )
            if retreat_err:
                messages.error(request, retreat_err)
                return HttpResponseRedirect(next_url)

            retreat_update_fields = []
            if (request.POST.get("requested_retreat_event_id") or "").strip() or (
                request.POST.get("requested_retreat_group_id") or ""
            ).strip():
                retreat_update_fields = [
                    "requested_retreat_participation",
                    "requested_retreat_event",
                    "requested_retreat_group",
                    "requested_retreat_role",
                    "updated_at",
                ]

            UserDivisionTeam.objects.update_or_create(
                user=profile.user,
                division=profile.requested_division,
                defaults={"team": team, "is_primary": True, "sort_order": 0},
            )
            from users.services.onboarding_approval import apply_pastoral_account_setup

            apply_pastoral_account_setup(profile.user, profile)
            profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
            profile.onboarding_note = note
            profile.save(
                update_fields=["onboarding_status", "onboarding_note", "updated_at"]
                + retreat_update_fields
            )
            sync_retreat_attendee_from_onboarding_profile(
                user=profile.user,
                profile=profile,
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
        ctx["allowed_divisions"] = list(
            allowed_divisions.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )
        ctx["active_division"] = active_division
        ctx["active_division_code"] = (
            active_division.code if active_division else self.ALL_DIVISIONS_CODE
        )
        ctx["all_divisions_code"] = self.ALL_DIVISIONS_CODE
        ctx["date_from"] = date_from
        ctx["date_to"] = date_to
        ctx["onboarding_status_choices"] = [
            (UserProfile.OnboardingStatus.PENDING, "승인 대기"),
            (UserProfile.OnboardingStatus.APPROVED, "승인 완료"),
            (UserProfile.OnboardingStatus.REJECTED, "반려"),
        ]
        ctx["status_filter"] = (self.request.GET.get("status") or "").strip()
        ctx["search_query"] = (self.request.GET.get("q") or "").strip()
        region_id_raw = (self.request.GET.get("region_id") or "").strip()
        if "region_id" in self.request.GET:
            ctx["active_region_id"] = region_id_raw if region_id_raw.isdigit() else ""
        elif active_division and active_division.region_id:
            ctx["active_region_id"] = str(active_division.region_id)
        else:
            ctx["active_region_id"] = ""

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
        else:
            scoped = scoped.filter(requested_division_id__in=self._allowed_division_ids())

        if ctx["active_region_id"]:
            scoped = scoped.filter(requested_division__region_id=int(ctx["active_region_id"]))

        search_q = ctx["search_query"]
        if search_q:
            from django.db.models import Q

            scoped = scoped.filter(
                Q(real_name__icontains=search_q)
                | Q(phone__icontains=search_q)
                | Q(requested_team__name__icontains=search_q)
                | Q(requested_division__name__icontains=search_q)
                | Q(requested_division__region__name__icontains=search_q)
                | Q(user__username__icontains=search_q)
            )

        _apps_order = ("-user__date_joined", "-id")
        status_filter = ctx["status_filter"]
        if status_filter == UserProfile.OnboardingStatus.PENDING:
            application_profiles = scoped.filter(
                onboarding_status=UserProfile.OnboardingStatus.PENDING
            ).order_by(*_apps_order)
        elif status_filter == UserProfile.OnboardingStatus.APPROVED:
            application_profiles = scoped.filter(
                onboarding_status=UserProfile.OnboardingStatus.APPROVED,
                updated_at__gte=start_dt,
                updated_at__lt=end_dt,
            ).order_by(*_apps_order)
        elif status_filter == UserProfile.OnboardingStatus.REJECTED:
            application_profiles = scoped.filter(
                onboarding_status=UserProfile.OnboardingStatus.REJECTED,
                updated_at__gte=start_dt,
                updated_at__lt=end_dt,
            ).order_by(*_apps_order)
        else:
            from django.db.models import Q

            application_profiles = scoped.filter(
                Q(onboarding_status=UserProfile.OnboardingStatus.PENDING)
                | Q(
                    onboarding_status__in=[
                        UserProfile.OnboardingStatus.APPROVED,
                        UserProfile.OnboardingStatus.REJECTED,
                    ],
                    updated_at__gte=start_dt,
                    updated_at__lt=end_dt,
                )
            ).order_by(*_apps_order)

        page_raw = (self.request.GET.get("page") or "1").strip()
        page_num = int(page_raw) if page_raw.isdigit() and int(page_raw) > 0 else 1
        paginator = Paginator(application_profiles, self._page_size)
        page_obj = paginator.get_page(page_num)
        application_profiles_page = list(page_obj.object_list)

        pending_profiles = [p for p in application_profiles_page if p.onboarding_status == UserProfile.OnboardingStatus.PENDING]
        approved_profiles = [p for p in application_profiles_page if p.onboarding_status == UserProfile.OnboardingStatus.APPROVED]
        rejected_profiles = [p for p in application_profiles_page if p.onboarding_status == UserProfile.OnboardingStatus.REJECTED]

        user_ids = {p.user_id for p in application_profiles_page if p.user_id}
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
        ctx["application_profiles"] = application_profiles_page
        ctx["page_obj"] = page_obj
        ctx["paginator"] = paginator
        ctx["is_paginated"] = paginator.num_pages > 1
        ctx["applications_query_base"] = self._applications_query_base()
        ctx["page_size"] = self._page_size
        ctx["user_label_map"] = label_map
        ctx["user_real_name_map"] = real_name_map

        status_label = {code: label for code, label in ctx["onboarding_status_choices"]}

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
        profile_kakao_map = {}
        profile_account_map = {}
        detail_map = {}
        for p in application_profiles_page:
            label = _profile_label(p)
            real_name = (p.real_name or "").strip()
            # 셀에는 실명을 우선 표시하고, 없으면 표시명/계정명으로 폴백한다.
            profile_label_map[p.id] = real_name or label
            profile_real_name_map[p.id] = real_name
            profile_kakao_map[p.id] = kakao_map.get(p.user_id, "")
            profile_account_map[p.id] = (getattr(p.user, "username", "") or "").strip()
            div = p.requested_division
            region_name = ""
            if div and div.region_id:
                try:
                    region_name = div.region.name
                except Exception:
                    region_name = ""
            applicant_role = p.requested_applicant_role or UserProfile.ApplicantRole.MEMBER
            applicant_role_label = dict(UserProfile.ApplicantRole.choices).get(
                applicant_role, "성도"
            )
            is_pastoral_applicant_row = applicant_role in (
                UserProfile.ApplicantRole.PASTOR,
                UserProfile.ApplicantRole.EVANGELIST,
            )
            detail_map[p.id] = {
                "profile_id": p.id,
                "label": label,
                "real_name": real_name,
                "display_name": (p.display_name or "").strip(),
                "phone": _phone_for_display((p.phone or "").strip()),
                "kakao_account": _kakao_account_display(
                    getattr(p.user, "username", "") if p.user_id else ""
                ),
                "kakao_nickname": kakao_map.get(p.user_id, ""),
                "linked_account": bool(p.user_id),
                "region_id": div.region_id if div and div.region_id else None,
                "region": region_name,
                "division_id": div.id if div else None,
                "division": div.name if div else "",
                "team_id": p.requested_team_id,
                "team": p.requested_team.name if p.requested_team_id else "",
                "applicant_role": applicant_role,
                "applicant_role_label": applicant_role_label,
                "is_pastoral_applicant": is_pastoral_applicant_row,
                "onboarding_status": p.onboarding_status,
                "status": status_label.get(p.onboarding_status, p.onboarding_status),
                "note": (p.onboarding_note or "").strip(),
                "retreat_participation": bool(p.requested_retreat_participation),
                "retreat_event_id": p.requested_retreat_event_id,
                "retreat_group_id": p.requested_retreat_group_id,
                "retreat_event": p.requested_retreat_event.name if p.requested_retreat_event_id else "",
                "retreat_group": p.requested_retreat_group.name if p.requested_retreat_group_id else "",
                "retreat_assign_note": (
                    "목회자 — 조원 자동 배정 없음"
                    if is_pastoral_applicant_row
                    else "승인 시 조원으로 배정"
                ),
                "date_joined": _fmt_dt(getattr(p.user, "date_joined", None)),
                "updated_at": _fmt_dt(p.updated_at),
            }
        ctx["user_detail_json"] = json.dumps(detail_map, ensure_ascii=False)
        ctx["application_edit_json"] = ctx["user_detail_json"]
        ctx["profile_label_map"] = profile_label_map
        ctx["profile_real_name_map"] = profile_real_name_map
        ctx["profile_kakao_map"] = profile_kakao_map
        ctx["profile_account_map"] = profile_account_map

        ctx["account_tab"] = "applications"
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
        allowed_division_id_set = self._allowed_division_ids()
        for t in Team.objects.filter(division_id__in=allowed_division_id_set).select_related(
            "division"
        ).order_by("division__sort_order", "sort_order", "name"):
            team_map.setdefault(str(t.division_id), []).append({"id": t.id, "name": t.name})
        ctx["teams_map_json"] = json.dumps(team_map, ensure_ascii=False)

        divisions_map: dict[str, list] = {}
        for d in allowed_divisions.select_related("region").order_by(
            "region__sort_order", "sort_order", "name"
        ):
            divisions_map.setdefault(str(d.region_id), []).append({"id": d.id, "name": d.name})
        ctx["divisions_map_json"] = json.dumps(divisions_map, ensure_ascii=False)

        retreat_events = list(
            RetreatEvent.objects.filter(is_active=True).order_by("-start_date", "-id")
        )
        ctx["retreat_events_json"] = json.dumps(
            [{"id": e.id, "name": e.name} for e in retreat_events],
            ensure_ascii=False,
        )
        retreat_groups = list(
            RetreatGroup.objects.filter(
                event__in=retreat_events, division_id__in=allowed_division_id_set
            )
            .select_related("event", "region", "division")
            .order_by("event_id", "region__sort_order", "division__sort_order", "order", "id")
        )
        ctx["retreat_groups_json"] = json.dumps(
            [
                {
                    "id": g.id,
                    "event_id": g.event_id,
                    "division_id": g.division_id,
                    "label": g.name,
                }
                for g in retreat_groups
            ],
            ensure_ascii=False,
        )
        ctx["activity_log_url"] = reverse("user_onboarding_application_activity_log")
        return ctx


class OnboardingApplicationActivityLogView(LoginRequiredMixin, TemplateView):
    """가입신청서 활동 로그(집계형) JSON."""

    login_url = reverse_lazy("user_login")

    def dispatch(self, request, *args, **kwargs):
        if not can_access_onboarding_approvals(request.user):
            raise PermissionDenied("가입신청서 페이지 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        profile_id_raw = (request.GET.get("profile_id") or "").strip()
        if not profile_id_raw.isdigit():
            return JsonResponse({"error": "profile_id가 올바르지 않습니다."}, status=400)

        allowed_ids = set(
            onboarding_approval_divisions_for(request.user).values_list("pk", flat=True)
        )
        profile = UserProfile.objects.filter(pk=int(profile_id_raw)).first()
        if profile is None:
            return JsonResponse({"error": "대상을 찾을 수 없습니다."}, status=404)
        if not profile.requested_division_id or profile.requested_division_id not in allowed_ids:
            return JsonResponse({"error": "권한이 없습니다."}, status=403)

        items = build_onboarding_application_activity_log(profile)
        if not items:
            items = [
                _activity_item(
                    at_dt=None,
                    actor="-",
                    summary="표시할 활동 기록이 없습니다.",
                    actor_kind="system",
                    category="기타 변경",
                    tone="other",
                )
            ]
        return JsonResponse({"items": items})


class DivisionAccountActivityLogView(LoginRequiredMixin, TemplateView):
    """계정 관리 활동 로그 페이지."""

    template_name = "users/account_activity_log.html"
    login_url = reverse_lazy("user_login")

    def _manageable_divisions(self):
        if is_platform_admin(self.request.user):
            return Division.objects.all()
        return membership_divisions_for(self.request.user)

    def _resolve_target_user(self):
        user_id_raw = (self.request.GET.get("user_id") or "").strip()
        if not user_id_raw.isdigit():
            return None, JsonResponse({"error": "user_id가 올바르지 않습니다."}, status=400)

        manageable = self._manageable_divisions()
        target_user = (
            User.objects.filter(pk=int(user_id_raw), is_active=True)
            .select_related("profile", "role_level")
            .first()
        )
        if target_user is None:
            return None, JsonResponse({"error": "대상을 찾을 수 없습니다."}, status=404)
        if not target_user.division_teams.filter(division__in=manageable).exists():
            return None, JsonResponse({"error": "권한이 없습니다."}, status=403)
        return target_user, None

    def dispatch(self, request, *args, **kwargs):
        if not can_manage_division_accounts(request.user):
            raise PermissionDenied("계정 관리 페이지 권한이 없습니다.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        target_user, error_response = self._resolve_target_user()
        if error_response is not None:
            wants_json = (
                request.GET.get("format") == "json"
                or "application/json" in (request.headers.get("Accept") or "")
            )
            if wants_json:
                return error_response
            raise Http404("활동 로그 대상을 찾을 수 없습니다.")

        profile = ensure_user_profile(target_user)
        items = build_onboarding_application_activity_log(profile)
        if not items:
            items = [
                _activity_item(
                    at_dt=None,
                    actor="-",
                    summary="표시할 활동 기록이 없습니다.",
                    actor_kind="system",
                    category="기타 변경",
                    tone="other",
                )
            ]

        wants_json = (
            request.GET.get("format") == "json"
            or "application/json" in (request.headers.get("Accept") or "")
        )
        if wants_json:
            return JsonResponse({"items": items})

        division_code = (request.GET.get("division_code") or "").strip()
        return_params = {"open_user": str(target_user.id), "view": "activity"}
        if division_code:
            return_params["division_code"] = division_code
        return HttpResponseRedirect(
            f"{reverse('user_division_account_roles')}?{urlencode(return_params)}"
        )


# 이전 URL·import 호환
OnboardingApprovalListView = OnboardingApplicationsListView


class DivisionAccountRoleManageView(LoginRequiredMixin, TemplateView):
    """목사/전도사/관리자용 부서 계정 직책 관리."""

    template_name = "users/division_account_roles.html"
    login_url = reverse_lazy("user_login")
    ALL_DIVISIONS_CODE = "__all__"

    def _manageable_divisions(self):
        # 스태프(슈퍼유저·is_staff)는 전체 부서, 계정 권한 보유자는 소속 부서만.
        if is_platform_admin(self.request.user):
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

        requested_code = (
            self.request.GET.get("division_code")
            or self.request.POST.get("division_code")
            or ""
        ).strip()
        can_all = is_platform_admin(self.request.user) or divisions.count() > 1
        # "전체" 선택 시 담당 부서 전체를 한 번에 조회한다(active_division=None).
        if can_all and requested_code == self.ALL_DIVISIONS_CODE:
            return None, divisions
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
        manageable = self._manageable_divisions()
        active_division, _ = self._resolve_active_division()
        requested_code = (request.POST.get("division_code") or "").strip()
        all_mode = (
            active_division is None
            and manageable.exists()
            and requested_code == self.ALL_DIVISIONS_CODE
        )

        if active_division is None and not all_mode:
            messages.error(request, "관리 가능한 부서가 없습니다.")
            return HttpResponseRedirect(reverse_lazy("user_division_account_roles"))

        if all_mode:
            redirect_url = (
                f"{reverse_lazy('user_division_account_roles')}"
                f"?division_code={self.ALL_DIVISIONS_CODE}"
            )
        else:
            redirect_url = self._roles_redirect(active_division)
        user_id = (request.POST.get("user_id") or "").strip()
        team_id = (request.POST.get("team_id") or "").strip()
        division_id_raw = (request.POST.get("division_id") or "").strip()
        valid_role_codes = set(Role.objects.values_list("code", flat=True))
        selected_role_codes = [c for c in request.POST.getlist("role_codes") if c in valid_role_codes]
        manage_attendance = request.POST.get("can_manage_attendance") == "on"
        manage_parking = request.POST.get("can_manage_parking") == "on"
        manage_accounts = request.POST.get("can_manage_accounts") == "on"
        manage_notices = request.POST.get("can_manage_notices") == "on"
        real_name = (request.POST.get("real_name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        retreat_group_id = (request.POST.get("retreat_group_id") or "").strip()
        retreat_role = (request.POST.get("retreat_role") or "").strip()
        role_level_id_raw = (request.POST.get("role_level_id") or "").strip()

        if not user_id.isdigit():
            messages.error(request, "대상 사용자를 선택해 주세요.")
            return HttpResponseRedirect(redirect_url)

        target_user = User.objects.filter(pk=int(user_id), is_active=True).first()
        if target_user is None:
            messages.error(request, "대상 사용자를 찾을 수 없습니다.")
            return HttpResponseRedirect(redirect_url)
        if all_mode:
            # "전체" 모드에서는 대상 사용자가 소속된 관리 가능 부서 중
            # 대표(우선) 멤버십 부서를 기준 부서로 삼는다.
            base_division_id = (
                target_user.division_teams.filter(division__in=manageable)
                .order_by("-is_primary", "sort_order", "id")
                .values_list("division_id", flat=True)
                .first()
            )
            if base_division_id is None:
                messages.error(request, "선택한 부서 소속 계정만 수정할 수 있습니다.")
                return HttpResponseRedirect(redirect_url)
            active_division = Division.objects.get(pk=base_division_id)
        if not target_user.division_teams.filter(division=active_division).exists():
            messages.error(request, "선택한 부서 소속 계정만 수정할 수 있습니다.")
            return HttpResponseRedirect(redirect_url)

        target_division = active_division
        if is_platform_admin(request.user) and division_id_raw.isdigit():
            new_division = Division.objects.filter(pk=int(division_id_raw)).first()
            if new_division is None:
                messages.error(request, "선택한 부서를 찾을 수 없습니다.")
                return HttpResponseRedirect(redirect_url)
            target_division = new_division
        elif division_id_raw.isdigit() and int(division_id_raw) != active_division.id:
            messages.error(request, "부서 이동은 스태프(관리자)만 가능합니다.")
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
        if target_user.can_manage_notices != manage_notices:
            target_user.can_manage_notices = manage_notices
            user_updates.append("can_manage_notices")
        new_role_level = None
        if role_level_id_raw.isdigit():
            new_role_level = RoleLevel.objects.filter(pk=int(role_level_id_raw)).first()
            if new_role_level is None:
                messages.error(request, "선택한 직급을 찾을 수 없습니다.")
                return HttpResponseRedirect(redirect_url)
        if target_user.role_level_id != (new_role_level.id if new_role_level else None):
            target_user.role_level = new_role_level
            user_updates.append("role_level")
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
            normalized = normalize_korea_mobile_phone(phone)
            if normalized is None:
                messages.error(request, "휴대폰 번호 형식이 올바르지 않습니다.")
                return HttpResponseRedirect(redirect_url)
            profile.phone = normalized
            prof_updates.append("phone")

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
                appoint_leadership=True,
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
            is_platform_admin(self.request.user)
            or getattr(self.request.user, "can_manage_accounts", False)
            or allowed_divisions.count() > 1
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
        if is_platform_admin(self.request.user):
            division_choices = list(
                Division.objects.select_related("region").order_by(
                    "region__sort_order", "sort_order", "name"
                )
            )

        team_map: dict[str, list] = {}
        team_name_by_id: dict[int, str] = {}
        for team in Team.objects.select_related("division").order_by(
            "division__sort_order", "sort_order", "name"
        ):
            team_map.setdefault(str(team.division_id), []).append(
                {"id": team.id, "name": team.name}
            )
            team_name_by_id[team.id] = team.name

        users_payload = []
        account_details: dict[int, dict] = {}

        # 단일 부서면 그 부서만, "전체"면 관리 가능한 모든 부서를 대상으로 한다.
        division_by_id = {d.id: d for d in division_choices}
        if active_division and active_division.id not in division_by_id:
            division_by_id[active_division.id] = active_division
        if active_division:
            target_division_ids = [active_division.id]
        else:
            target_division_ids = [d.id for d in allowed_divisions]

        if target_division_ids:
            # 사용자당 대표(우선) 멤버십 부서를 1개만 고른다(전체 모드 중복 방지).
            rep_division_by_user: dict[int, int] = {}
            rep_team_by_user: dict[int, int | None] = {}
            for row in (
                UserDivisionTeam.objects.filter(
                    division_id__in=target_division_ids, user__is_active=True
                )
                .order_by("-is_primary", "division__sort_order", "sort_order", "id")
                .values("user_id", "division_id", "team_id")
            ):
                if row["user_id"] in rep_division_by_user:
                    continue
                rep_division_by_user[row["user_id"]] = row["division_id"]
                rep_team_by_user[row["user_id"]] = row["team_id"]

            user_ids = list(rep_division_by_user.keys())
            user_qs = (
                User.objects.filter(pk__in=user_ids, is_active=True)
                .select_related(
                    "role_level",
                    "profile",
                    "profile__requested_division__region",
                    "profile__requested_team",
                    "profile__requested_retreat_event",
                    "profile__requested_retreat_group",
                )
                .order_by("username")
            )

            retreat_membership_map: dict[int, tuple[int | None, str]] = {}
            if active_retreat:
                for mem in RetreatGroupMembership.objects.filter(
                    user_id__in=user_ids, group__event=active_retreat
                ).select_related("group"):
                    retreat_membership_map[mem.user_id] = (mem.group_id, mem.role)

            # 대표 부서별 기능부서(FunctionalDepartment) → 직책(Role) 매핑.
            rep_division_ids = set(rep_division_by_user.values())
            dept_by_division = {
                d_id: self._division_functional_department(division_by_id[d_id])
                for d_id in rep_division_ids
                if d_id in division_by_id
            }
            dept_division_by_dept_id = {
                dept.id: d_id for d_id, dept in dept_by_division.items()
            }
            role_map: dict[int, set[str]] = {}
            if dept_by_division:
                for link in UserFunctionalDeptRole.objects.filter(
                    user_id__in=user_ids,
                    functional_department_id__in=[
                        d.id for d in dept_by_division.values()
                    ],
                ).select_related("role"):
                    if (
                        dept_division_by_dept_id.get(link.functional_department_id)
                        == rep_division_by_user.get(link.user_id)
                    ):
                        role_map.setdefault(link.user_id, set()).add(link.role.code)

            kakao_nickname_by_user = kakao_nickname_map_for_user_ids(user_ids)
            memberships_detail: dict[int, list] = {}
            for udt in UserDivisionTeam.objects.filter(
                user_id__in=user_ids
            ).select_related("division", "division__region", "team"):
                memberships_detail.setdefault(udt.user_id, []).append(
                    {
                        "division": (
                            f"{udt.division.region.name} · {udt.division.name}"
                            if udt.division_id and udt.division.region_id
                            else (udt.division.name if udt.division_id else "")
                        ),
                        "team": udt.team.name if udt.team_id else "",
                        "is_primary": bool(getattr(udt, "is_primary", False)),
                    }
                )

            for u in user_qs:
                prof = getattr(u, "profile", None)
                rep_division = division_by_id.get(rep_division_by_user.get(u.id))
                region_id = rep_division.region_id if rep_division else None
                region_name = (
                    rep_division.region.name if rep_division and region_id else ""
                )
                division_id = rep_division.id if rep_division else None
                division_name = rep_division.name if rep_division else ""
                team_id = rep_team_by_user.get(u.id)
                team_name = team_name_by_id.get(team_id, "") if team_id else ""
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
                        "phone": _phone_for_display(getattr(prof, "phone", "") or ""),
                        "kakao_uid": u.username[6:]
                        if u.username.startswith("kakao_")
                        else "",
                        "region_id": region_id,
                        "region_name": region_name,
                        "division_id": division_id,
                        "division_name": division_name,
                        "team_id": team_id,
                        "team_name": team_name,
                        "date_joined": timezone.localtime(u.date_joined).strftime("%Y-%m-%d")
                        if u.date_joined
                        else "",
                    }
                )
                assigned_codes = sorted(list(role_map.get(u.id, set())))
                created_at = ""
                if u.date_joined:
                    created_at = timezone.localtime(u.date_joined).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                updated_at = ""
                if prof and getattr(prof, "updated_at", None):
                    updated_at = timezone.localtime(prof.updated_at).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                last_updated_label = ""
                if prof and getattr(prof, "updated_at", None):
                    last_updated_label = _activity_date_label(prof.updated_at)
                elif u.date_joined:
                    last_updated_label = _activity_date_label(u.date_joined)
                from users.services.onboarding_approval import signup_application_detail

                account_details[u.id] = {
                    "username": u.username,
                    "kakao_uid": u.username[6:]
                    if u.username.startswith("kakao_")
                    else "",
                    "first_name": u.first_name or "",
                    "last_name": u.last_name or "",
                    "email": u.email or "",
                    "role_level": getattr(u.role_level, "name", "") or "",
                    "role_level_id": u.role_level_id,
                    "signup_source": u.get_signup_source_display(),
                    "is_superuser": bool(u.is_superuser),
                    "display_name": (getattr(prof, "display_name", "") or "").strip()
                    or kakao_nickname_by_user.get(u.id, ""),
                    "real_name": (getattr(prof, "real_name", "") or "").strip(),
                    "phone": _phone_for_display(getattr(prof, "phone", "") or ""),
                    "region_id": region_id,
                    "region_name": region_name,
                    "division_id": division_id,
                    "division_name": division_name,
                    "team_id": team_id,
                    "team_name": team_name,
                    "retreat_group_id": retreat_group_id,
                    "retreat_role": retreat_role,
                    "can_manage_attendance": bool(
                        getattr(u, "can_manage_attendance", False)
                    ),
                    "can_manage_parking": bool(
                        getattr(u, "can_manage_parking", False)
                    ),
                    "can_manage_accounts": bool(
                        getattr(u, "can_manage_accounts", False)
                    ),
                    "can_manage_notices": bool(
                        getattr(u, "can_manage_notices", False)
                    ),
                    "assigned_role_codes": assigned_codes,
                    "memberships": memberships_detail.get(u.id, []),
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "updated_at_label": last_updated_label,
                    "avatar_url": user_profile_avatar_url(u),
                    "event_name": active_retreat.name if active_retreat else "",
                    "signup_application": signup_application_detail(prof),
                }

        region_qs = Region.objects.all().order_by("sort_order", "name")
        if not is_platform_admin(self.request.user) and active_division and active_division.region_id:
            region_qs = Region.objects.filter(pk=active_division.region_id)

        ctx["allowed_divisions"] = division_choices
        ctx["active_division"] = active_division
        ctx["all_divisions_code"] = self.ALL_DIVISIONS_CODE
        ctx["active_division_code"] = (
            active_division.code if active_division else self.ALL_DIVISIONS_CODE
        )
        ctx["can_choose_division"] = can_choose_division
        ctx["can_move_division"] = is_platform_admin(self.request.user)
        ctx["users_payload"] = users_payload
        ctx["account_details_json"] = json.dumps(account_details, ensure_ascii=False)
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
        ctx["role_level_choices"] = list(
            RoleLevel.objects.order_by("-level", "sort_order")
        )
        ctx["account_tab"] = "roles"
        ctx["role_options_api_url"] = reverse_lazy("api_user_assignable_roles")
        ctx["activity_log_url"] = reverse("user_division_account_activity_log")
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
