"""Slack Web API client."""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils.functional import LazyObject
from slack_sdk import WebClient

from utils.slack.blocks import get_staff_application_blocks, get_user_signup_blocks

logger = logging.getLogger(__name__)


class SlackClient:
    def __init__(self, token: str):
        self.client = WebClient(token=token)

    def send_message(self, channel: str, text: str, blocks=None) -> None:
        if not getattr(settings, "SLACK_NOTIFICATIONS_ENABLED", True):
            return
        try:
            channel_dict = {
                "local": "#231_개발팀_local",
                "dev": "#232_개발팀_dev",
            }
            channel = channel_dict.get(settings.ENV, channel)
            self.client.chat_postMessage(channel=channel, text=text, blocks=blocks)
        except Exception:
            logger.exception(
                "slack send_message failed channel=%s text=%s", channel, text
            )

    def send_user_signup(self, user) -> None:
        self.send_message(
            channel="#500_회원가입_알림",
            text="회원가입 알림",
            blocks=get_user_signup_blocks(user),
        )

    def send_staff_application(self, application) -> None:
        self.send_message(
            channel="#501_수련회_운영진_참가신청_알림",
            text="수련회 운영진 참가 신청 알림",
            blocks=get_staff_application_blocks(application),
        )


class LazySlackClient(LazyObject):
    def _setup(self):
        self._wrapped = SlackClient(settings.SLACK_TOKEN)


slack_client = LazySlackClient()
