"""관리자: 교적(Member) 부서·팀 이동."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from registry.forms.member_org_move import (
    MemberOrgDivisionTransferForm,
    MemberOrgTeamChangeForm,
)
from registry.models import Member
from registry.services.member_org import (
    change_team_within_division as change_member_team,
    transfer_to_division as transfer_member_division,
)


def _flash_validation(request, e: ValidationError) -> None:
    if hasattr(e, "error_dict"):
        for field, errs in e.error_dict.items():
            for err in errs:
                messages.error(request, f"{field}: {err}")
    else:
        for msg in e.messages:
            messages.error(request, msg)


@staff_member_required
def member_org_move_dashboard(request):
    return render(
        request,
        "admin/registry/member_org_move_dashboard.html",
        {
            "title": "교적 — 부서·팀 이동",
            "opts": Member._meta,
        },
    )


@staff_member_required
def member_org_move_detail(request, object_id):
    try:
        pk = int(object_id)
    except (TypeError, ValueError) as e:
        raise Http404 from e
    member = get_object_or_404(Member, pk=pk)
    change_form = MemberOrgTeamChangeForm(initial={"member": member})
    transfer_form = MemberOrgDivisionTransferForm(initial={"member": member})

    if request.method == "POST":
        kind = request.POST.get("form")
        if kind == "change_team":
            change_form = MemberOrgTeamChangeForm(request.POST)
            transfer_form = MemberOrgDivisionTransferForm(initial={"member": member})
            if change_form.is_valid():
                cd = change_form.cleaned_data
                try:
                    change_member_team(
                        cd["member"],
                        cd["division"],
                        cd["new_team"],
                        membership=cd.get("membership") or None,
                        make_primary=cd["make_primary"],
                    )
                except ValidationError as e:
                    _flash_validation(request, e)
                else:
                    messages.success(request, "같은 부서 내 팀을 변경했습니다.")
                    return HttpResponseRedirect(request.path)
        elif kind == "transfer":
            transfer_form = MemberOrgDivisionTransferForm(request.POST)
            change_form = MemberOrgTeamChangeForm(initial={"member": member})
            if transfer_form.is_valid():
                cd = transfer_form.cleaned_data
                try:
                    transfer_member_division(
                        cd["member"],
                        from_division=cd.get("from_division"),
                        to_division=cd["to_division"],
                        team=cd.get("team"),
                        remove_from_source=bool(cd.get("remove_from_source")),
                        make_primary=bool(cd.get("make_primary")),
                    )
                except ValidationError as e:
                    _flash_validation(request, e)
                else:
                    messages.success(request, "부서 이동을 반영했습니다.")
                    return HttpResponseRedirect(request.path)

    memberships = member.division_teams.select_related("division", "team").order_by(
        "-is_primary", "division__name", "team__name"
    )
    return render(
        request,
        "admin/registry/member_org_move_detail.html",
        {
            "title": f"교적 부서·팀 이동 — {member.name}",
            "member_obj": member,
            "change_form": change_form,
            "transfer_form": transfer_form,
            "memberships": memberships,
            "back_url": reverse("admin:registry_member_change", args=[member.pk]),
            "opts": Member._meta,
        },
    )
