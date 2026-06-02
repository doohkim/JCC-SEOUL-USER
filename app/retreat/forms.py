"""수련회 폼."""

from __future__ import annotations

from django import forms

from retreat.models import RetreatEvent


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
