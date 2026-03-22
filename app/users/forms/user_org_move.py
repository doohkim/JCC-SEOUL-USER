"""앱 사용자(User) 부서·팀 이동 폼."""

from django import forms
from django.contrib.auth import get_user_model

from users.models import Division, Team, UserDivisionTeam

User = get_user_model()


class UserOrgTeamChangeForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.all(), label="사용자")
    division = forms.ModelChoiceField(queryset=Division.objects.all(), label="부서")
    membership = forms.ModelChoiceField(
        queryset=UserDivisionTeam.objects.none(),
        required=False,
        label="바꿀 소속 행",
    )
    new_team = forms.ModelChoiceField(
        queryset=Team.objects.select_related("division"),
        label="새 팀",
    )
    make_primary = forms.BooleanField(initial=True, required=False, label="주 소속으로")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uid = None
        if self.is_bound and self.data.get("user"):
            uid = self.data.get("user")
        elif not self.is_bound and self.initial.get("user") is not None:
            u = self.initial["user"]
            uid = u.pk if hasattr(u, "pk") else u
        if uid:
            self.fields["membership"].queryset = UserDivisionTeam.objects.filter(
                user_id=uid
            ).select_related("division", "team")

    def clean(self):
        cleaned = super().clean()
        division = cleaned.get("division")
        team = cleaned.get("new_team")
        if division and team and team.division_id != division.id:
            self.add_error("new_team", "팀이 해당 부서에 속하지 않습니다.")
        return cleaned


class UserOrgDivisionTransferForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.all(), label="사용자")
    from_division = forms.ModelChoiceField(
        queryset=Division.objects.all(),
        required=False,
        label="이전 부서",
    )
    to_division = forms.ModelChoiceField(queryset=Division.objects.all(), label="목적 부서")
    team = forms.ModelChoiceField(
        queryset=Team.objects.select_related("division"),
        required=False,
        label="목적 팀",
    )
    remove_from_source = forms.BooleanField(initial=True, required=False)
    make_primary = forms.BooleanField(initial=True, required=False)

    def clean(self):
        cleaned = super().clean()
        to_div = cleaned.get("to_division")
        team = cleaned.get("team")
        if to_div and team and team.division_id != to_div.id:
            self.add_error("team", "목적 팀은 목적 부서에 속해야 합니다.")
        return cleaned
