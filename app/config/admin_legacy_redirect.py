"""
앱 분리 이전 Admin URL 호환.

예: ``/admin/users/attendanceweek/1/change/`` → ``/admin/attendance/attendanceweek/1/change/``
북마크·로그인 next 파라미터 등으로 옛 주소가 남은 경우 404 방지.
"""

from __future__ import annotations

import re

from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET

# 옛 app_label=users 에 있던 모델 → 새 app_label
LEGACY_ADMIN_MODEL_APP: dict[str, str] = {
    # attendance
    "attendanceweek": "attendance",
    "midweekattendancerecord": "attendance",
    "sundayattendanceline": "attendance",
    "worshiprosterscope": "attendance",
    "worshiprosterentry": "attendance",
    "teamattendancesession": "attendance",
    "teammemberslotattendance": "attendance",
    # registry (긴 이름부터 매칭되도록 아래에서 정렬)
    "memberdivisionteam": "registry",
    "memberfunctionaldeptrole": "registry",
    "memberfamilymember": "registry",
    "membervisitlog": "registry",
    "memberprofile": "registry",
    "memberclub": "registry",
    "member": "registry",
}

_LEGACY_MODELS_SORTED = sorted(LEGACY_ADMIN_MODEL_APP.keys(), key=len, reverse=True)
LEGACY_USERS_ADMIN_PATTERN = (
    r"^admin/users/(?P<model>"
    + "|".join(re.escape(m) for m in _LEGACY_MODELS_SORTED)
    + r")(?P<rest>/.*)?$"
)


@require_GET
def redirect_legacy_users_admin(request, model, rest=None):
    suffix = rest if rest else "/"
    app = LEGACY_ADMIN_MODEL_APP.get(model)
    if not app:
        return HttpResponseRedirect("/admin/")
    return HttpResponseRedirect(f"/admin/{app}/{model}{suffix}")
