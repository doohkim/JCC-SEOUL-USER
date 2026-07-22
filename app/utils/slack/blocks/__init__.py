"""Slack Block Kit builders."""

from __future__ import annotations

from django.conf import settings
from django.urls import reverse

from retreat.models import StaffApplicationTrack


def public_site_base_url() -> str:
    env = getattr(settings, "ENV", "local")
    if env == "local":
        return "http://localhost:8000"
    if env == "dev":
        return "https://shalom.dev.jcc-seoul.com:8443"
    return "https://shalom.jcc-seoul.com"


def _absolute_url(path: str) -> str:
    base = public_site_base_url().rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def _section_blocks(
    info_lines: list[str], button_text: str, button_url: str
) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(info_lines),
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": button_text,
                        "emoji": True,
                    },
                    "value": "button_admin_url",
                    "url": button_url,
                },
            ],
        },
    ]


def get_user_signup_blocks(user) -> list[dict]:
    profile = getattr(user, "profile", None)
    display_name = ""
    phone = ""
    if profile is not None:
        display_name = (profile.display_name or profile.real_name or "").strip()
        phone = (profile.phone or "").strip()

    signup_source = ""
    if hasattr(user, "get_signup_source_display"):
        signup_source = user.get_signup_source_display()
    elif getattr(user, "signup_source", None):
        signup_source = str(user.signup_source)

    date_joined = getattr(user, "date_joined", None)
    joined_text = date_joined.isoformat() if date_joined else "-"

    info_lines = [
        "*회원가입 알림*",
        f"표시명: {display_name or '-'}",
        f"username: {user.username}",
        f"가입 경로: {signup_source or '-'}",
        f"이메일: {user.email or '-'}",
        f"휴대폰: {phone or '-'}",
        f"가입 시각: {joined_text}",
    ]
    return _section_blocks(
        info_lines,
        button_text="가입신청 목록에서 확인",
        button_url=_absolute_url(reverse("user_onboarding_applications")),
    )


def get_staff_application_blocks(application) -> list[dict]:
    user = application.user
    profile = getattr(user, "profile", None)
    display_name = ""
    if profile is not None:
        display_name = (profile.display_name or profile.real_name or "").strip()
    applicant_label = display_name or user.get_username()

    track = application.application_track
    track_label = dict(StaffApplicationTrack.choices).get(track, track or "-")
    group_name = application.group.name if application.group_id else "-"
    group_role = application.get_group_role_display() if application.group_role else "-"
    status_label = application.get_status_display()

    info_lines = [
        "*수련회 운영진 참가 신청 알림*",
        f"집회: {application.event.name}",
        f"신청자: {applicant_label} ({user.username})",
        f"지역: {application.region}",
        f"부서: {application.division}",
        f"신청 유형: {track_label}",
        f"조: {group_name}",
        f"조 역할: {group_role}",
        f"상태: {status_label}",
    ]
    return _section_blocks(
        info_lines,
        button_text="참가 신청 목록에서 확인",
        button_url=_absolute_url(
            reverse("retreat_staff_applications", args=[application.event_id])
        ),
    )
