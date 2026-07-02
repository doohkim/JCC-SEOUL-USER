"""수련회 폼."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from retreat.models import RetreatEvent, RetreatGroup, RetreatGroupMembership, RetreatStaffApplication
from retreat.services.staff_application import (
    eligible_groups_for_member,
    is_pastoral_staff_applicant,
    member_can_apply_to_event,
    primary_affiliation_for,
    staff_applicant_tier,
    validate_member_group_choice,
)


class RetreatApplyForm(forms.Form):
    requested_retreat_participation = forms.BooleanField(
        label="수련회 참여",
        required=False,
    )
    requested_retreat_role = forms.ChoiceField(
        label="희망 역할",
        choices=[
            ("", "참가자(일반)"),
            ("leader", "조장"),
            ("vice_leader", "부조장"),
        ],
        required=False,
    )

    def __init__(self, *args, event: RetreatEvent | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event


class RetreatStaffApplicationForm(forms.Form):
    region = forms.IntegerField(widget=forms.HiddenInput)
    division = forms.IntegerField(widget=forms.HiddenInput)
    group = forms.ModelChoiceField(
        label="조",
        queryset=RetreatGroup.objects.none(),
        required=False,
        empty_label="선택",
    )
    group_role = forms.ChoiceField(
        label="직책",
        choices=[("", "선택"), *RetreatGroupMembership.Role.choices],
        required=False,
    )
    note = forms.CharField(
        label="지원 동기 및 한마디",
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "운영진으로 참여하고 싶은 이유를 간략히 적어주세요.",
            }
        ),
    )

    def __init__(
        self,
        *args,
        event: RetreatEvent,
        user,
        read_only: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.event = event
        self.user = user
        self.read_only = read_only
        self.applicant_tier = staff_applicant_tier(user)
        self.is_pastoral = is_pastoral_staff_applicant(user)
        self.affiliation_region, self.affiliation_division = primary_affiliation_for(
            user
        )

        if self.affiliation_region and self.affiliation_division:
            self.fields["region"].initial = self.affiliation_region.id
            self.fields["division"].initial = self.affiliation_division.id

        if self.is_pastoral:
            self.fields["group"].widget = forms.HiddenInput()
            self.fields["group_role"].widget = forms.HiddenInput()
        else:
            eligible = eligible_groups_for_member(user, event)
            self.fields["group"].queryset = RetreatGroup.objects.filter(
                pk__in=[g.id for g in eligible]
            ).order_by("order", "id")

        if read_only:
            for field in self.fields.values():
                field.disabled = True

    def clean_region(self):
        region, _division = primary_affiliation_for(self.user)
        if region is None:
            raise ValidationError("소속 지역이 등록되어 있지 않습니다.")
        submitted = self.cleaned_data.get("region")
        if submitted and int(submitted) != region.id:
            raise ValidationError("소속 지역을 변경할 수 없습니다.")
        return region.id

    def clean_division(self):
        _region, division = primary_affiliation_for(self.user)
        if division is None:
            raise ValidationError("소속 부서가 등록되어 있지 않습니다.")
        submitted = self.cleaned_data.get("division")
        if submitted and int(submitted) != division.id:
            raise ValidationError("소속 부서를 변경할 수 없습니다.")
        return division.id

    def clean(self):
        cleaned = super().clean()
        region, division = primary_affiliation_for(self.user)
        if region is None or division is None:
            raise ValidationError(
                "소속 지역·부서가 등록되어 있지 않습니다. 계정 관리자에게 문의해 주세요."
            )
        cleaned["region"] = region
        cleaned["division"] = division

        if not self.is_pastoral:
            can_apply, message = member_can_apply_to_event(self.user, self.event)
            if not can_apply:
                raise ValidationError(message)
            group = cleaned.get("group")
            group_role = cleaned.get("group_role")
            if not group:
                raise ValidationError({"group": "조를 선택해 주세요."})
            if not group_role:
                raise ValidationError({"group_role": "직책을 선택해 주세요."})
            try:
                validate_member_group_choice(
                    self.user, self.event, group, division=division
                )
            except ValueError as exc:
                raise ValidationError({"group": str(exc)}) from exc
        else:
            cleaned["group"] = None
            cleaned["group_role"] = ""
        return cleaned

    def save(self) -> RetreatStaffApplication:
        if RetreatStaffApplication.objects.filter(
            event=self.event,
            user=self.user,
            status__in=[
                RetreatStaffApplication.Status.PENDING,
                RetreatStaffApplication.Status.APPROVED,
            ],
        ).exists():
            raise ValidationError("이미 제출한 신청이 있습니다.")
        region = self.cleaned_data["region"]
        division = self.cleaned_data["division"]
        group = self.cleaned_data.get("group")
        return RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.user,
            region=region,
            division=division,
            group=None if self.is_pastoral else group,
            group_role="" if self.is_pastoral else self.cleaned_data.get("group_role"),
            note=(self.cleaned_data.get("note") or "").strip(),
            status=RetreatStaffApplication.Status.PENDING,
        )
