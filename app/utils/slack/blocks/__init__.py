"""Slack Block Kit builders.

Slack은 HTML/CSS를 지원하지 않으므로 header · fields · emoji · primary button 으로 구성한다.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

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


def _field(label: str, value: str, *, emoji: str = "") -> dict:
    prefix = f"{emoji} " if emoji else ""
    return {
        "type": "mrkdwn",
        "text": f"*{prefix}{label}*\n{value or '-'}",
    }


def _notification_blocks(
    *,
    header: str,
    fields: list[dict],
    button_text: str,
    button_url: str,
    context_lines: list[str] | None = None,
) -> list[dict]:
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header,
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": fields[:10],
        },
    ]
    if context_lines:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "  ·  ".join(context_lines),
                    }
                ],
            }
        )
    blocks.extend(
        [
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
                        "style": "primary",
                        "value": "button_admin_url",
                        "url": button_url,
                    },
                ],
            },
        ]
    )
    return blocks


def get_user_signup_blocks(user) -> list[dict]:
    profile = getattr(user, "profile", None)
    display_name = ""
    real_name = ""
    phone = ""
    if profile is not None:
        real_name = (profile.real_name or "").strip()
        display_name = (profile.display_name or profile.real_name or "").strip()
        phone = (profile.phone or "").strip()

    signup_source = ""
    if hasattr(user, "get_signup_source_display"):
        signup_source = user.get_signup_source_display()
    elif getattr(user, "signup_source", None):
        signup_source = str(user.signup_source)

    date_joined = getattr(user, "date_joined", None)
    if date_joined:
        joined_text = timezone.localtime(date_joined).strftime("%Y-%m-%d %H:%M")
    else:
        joined_text = "-"

    # 계정 관리(roles)는 슈퍼유저·계정관리 권한자만 접근 가능.
    search_name = real_name or display_name
    roles_path = reverse("user_division_account_roles")
    query = urlencode({"q": search_name, "division_code": "__all__"})

    return _notification_blocks(
        header="👋 회원가입 알림",
        fields=[
            _field("표시명", display_name or "-", emoji="👤"),
            _field("실명", real_name or "-", emoji="📝"),
            _field("username", user.username, emoji="🔑"),
            _field("가입 경로", signup_source or "-", emoji="🚪"),
            _field("이메일", user.email or "-", emoji="✉️"),
            _field("휴대폰", phone or "-", emoji="📱"),
        ],
        context_lines=[f"🕒 가입 시각: `{joined_text}`"],
        button_text="🔎 계정 관리에서 확인",
        button_url=_absolute_url(f"{roles_path}?{query}"),
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

    return _notification_blocks(
        header="🏕️ 수련회 운영진 참가 신청",
        fields=[
            _field("집회", application.event.name, emoji="📅"),
            _field("신청자", f"{applicant_label} (`{user.username}`)", emoji="👤"),
            _field("지역", str(application.region), emoji="📍"),
            _field("부서", str(application.division), emoji="🏢"),
            _field("신청 유형", track_label, emoji="🗂️"),
            _field("조 / 역할", f"{group_name} · {group_role}", emoji="👥"),
            _field("상태", status_label, emoji="⏳"),
        ],
        button_text="📋 참가 신청 목록에서 확인",
        button_url=_absolute_url(
            reverse("retreat_staff_applications", args=[application.event_id])
        ),
    )
