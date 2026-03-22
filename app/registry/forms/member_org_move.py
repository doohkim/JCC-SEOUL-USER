"""교적(Member) 부서·팀 이동 폼."""

from django import forms

from registry.models import Member, MemberDivisionTeam
from users.models import Division, Team


class MemberOrgTeamChangeForm(forms.Form):
    member = forms.ModelChoiceField(queryset=Member.objects.all(), label="멤버(교적)")
    division = forms.ModelChoiceField(queryset=Division.objects.all(), label="부서")
    membership = forms.ModelChoiceField(
        queryset=MemberDivisionTeam.objects.none(),
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
        mid = None
        if self.is_bound and self.data.get("member"):
            mid = self.data.get("member")
        elif not self.is_bound and self.initial.get("member") is not None:
            m = self.initial["member"]
            mid = m.pk if hasattr(m, "pk") else m
        if mid:
            self.fields["membership"].queryset = MemberDivisionTeam.objects.filter(
                member_id=mid
            ).select_related("division", "team")

    def clean(self):
        cleaned = super().clean()
        division = cleaned.get("division")
        team = cleaned.get("new_team")
        if division and team and team.division_id != division.id:
            self.add_error("new_team", "팀이 해당 부서에 속하지 않습니다.")
        return cleaned


class MemberOrgDivisionTransferForm(forms.Form):
    member = forms.ModelChoiceField(queryset=Member.objects.all(), label="멤버(교적)")
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
