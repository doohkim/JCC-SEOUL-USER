"""관리자: 앱 사용자(User) 부서·팀 이동."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from users.forms.user_org_move import (
    UserOrgDivisionTransferForm,
    UserOrgTeamChangeForm,
)
from users.services.user_org import (
    change_team_within_division as change_user_team,
    transfer_to_division as transfer_user_division,
)

User = get_user_model()


def _flash_validation(request, e: ValidationError) -> None:
    if hasattr(e, "error_dict"):
        for field, errs in e.error_dict.items():
            for err in errs:
                messages.error(request, f"{field}: {err}")
    else:
        for msg in e.messages:
            messages.error(request, msg)


@staff_member_required
def user_org_move_dashboard(request):
    return render(
        request,
        "admin/users/user_org_move_dashboard.html",
        {
            "title": "사용자 — 부서·팀 이동",
            "opts": User._meta,
        },
    )


@staff_member_required
def user_org_move_detail(request, object_id):
    try:
        pk = int(object_id)
    except (TypeError, ValueError) as e:
        raise Http404 from e
    user_obj = get_object_or_404(User, pk=pk)
    change_form = UserOrgTeamChangeForm(initial={"user": user_obj})
    transfer_form = UserOrgDivisionTransferForm(initial={"user": user_obj})

    if request.method == "POST":
        kind = request.POST.get("form")
        if kind == "change_team":
            change_form = UserOrgTeamChangeForm(request.POST)
            transfer_form = UserOrgDivisionTransferForm(initial={"user": user_obj})
            if change_form.is_valid():
                cd = change_form.cleaned_data
                try:
                    change_user_team(
                        cd["user"],
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
            transfer_form = UserOrgDivisionTransferForm(request.POST)
            change_form = UserOrgTeamChangeForm(initial={"user": user_obj})
            if transfer_form.is_valid():
                cd = transfer_form.cleaned_data
                try:
                    transfer_user_division(
                        cd["user"],
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

    memberships = user_obj.division_teams.select_related("division", "team").order_by(
        "-is_primary", "division__name", "team__name"
    )
    return render(
        request,
        "admin/users/user_org_move_detail.html",
        {
            "title": f"사용자 부서·팀 이동 — {user_obj.username}",
            "user_obj": user_obj,
            "change_form": change_form,
            "transfer_form": transfer_form,
            "memberships": memberships,
            "back_url": reverse("admin:users_user_change", args=[user_obj.pk]),
            "opts": User._meta,
        },
    )
