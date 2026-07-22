"""수련회 폼."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from retreat.models import (
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatStaffApplication,
    StaffApplicationTrack,
)
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
            ("teacher", "선생님"),
        ],
        required=False,
    )

    def __init__(self, *args, event: RetreatEvent | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event


class RetreatStaffApplicationForm(forms.Form):
    application_track = forms.ChoiceField(
        label="신청 유형",
        choices=[("", "선택"), *StaffApplicationTrack.choices],
        required=False,
    )
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
            self.fields["application_track"].widget = forms.HiddenInput()
            self.fields["group"].widget = forms.HiddenInput()
            self.fields["group_role"].widget = forms.HiddenInput()
        else:
            self.eligible_groups = eligible_groups_for_member(user, event)
            group_field = self.fields["group"]
            group_field.queryset = RetreatGroup.objects.filter(
                pk__in=[g.id for g in self.eligible_groups]
            ).order_by("order", "id")
            group_field.label_from_instance = lambda obj: obj.name
            for name in ("application_track", "group", "group_role"):
                self.fields[name].widget.attrs["data-cselect"] = ""
            if not read_only:
                self.fields["application_track"].initial = (
                    StaffApplicationTrack.GROUP_LEADERSHIP
                )

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
            eligible_groups = getattr(self, "eligible_groups", None)
            can_apply, message = member_can_apply_to_event(
                self.user, self.event, eligible_groups=eligible_groups
            )
            if not can_apply:
                raise ValidationError(message)
            track = (cleaned.get("application_track") or "").strip()
            if track not in StaffApplicationTrack.values:
                if not track:
                    track = StaffApplicationTrack.GROUP_LEADERSHIP
                else:
                    raise ValidationError(
                        {"application_track": "신청 유형을 선택해 주세요."}
                    )
            cleaned["application_track"] = track
            group = cleaned.get("group")
            group_role = cleaned.get("group_role")
            if track == StaffApplicationTrack.GROUP_LEADERSHIP:
                if not group:
                    raise ValidationError({"group": "조를 선택해 주세요."})
                if not group_role:
                    raise ValidationError({"group_role": "직책을 선택해 주세요."})
                try:
                    validate_member_group_choice(
                        self.user,
                        self.event,
                        group,
                        region=region,
                        division=division,
                        eligible_groups=eligible_groups,
                    )
                except ValueError as exc:
                    raise ValidationError({"group": str(exc)}) from exc
            else:
                cleaned["group"] = None
                cleaned["group_role"] = ""
        else:
            cleaned["application_track"] = StaffApplicationTrack.COUNCIL
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
        track = (
            self.cleaned_data.get("application_track") or StaffApplicationTrack.COUNCIL
        )
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.user,
            region=region,
            division=division,
            application_track=track,
            group=None if track != StaffApplicationTrack.GROUP_LEADERSHIP else group,
            group_role=(
                ""
                if track != StaffApplicationTrack.GROUP_LEADERSHIP
                else self.cleaned_data.get("group_role")
            ),
            status=RetreatStaffApplication.Status.PENDING,
        )
        from utils.slack import slack_client

        slack_client.send_staff_application(application)
        return application
