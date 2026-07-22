"""Slack 알림 클라이언트·블록 단위 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from retreat.forms import RetreatStaffApplicationForm
from retreat.models import (
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatStaffApplication,
    StaffApplicationTrack,
)
from users.mixins import ensure_user_profile
from users.models import Division, Region, UserDivisionTeam, UserProfile
from utils.slack.blocks import (
    get_staff_application_blocks,
    get_user_signup_blocks,
    public_site_base_url,
)
from utils.slack.client import SlackClient

User = get_user_model()


class SlackBlocksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.region, name="슬랙청년", code="slack_youth", sort_order=98
        )
        cls.event = RetreatEvent.objects.create(
            name="슬랙 수련회",
            start_date=date(2027, 8, 1),
            end_date=date(2027, 8, 3),
            staff_applications_open=True,
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.region,
            division=cls.division,
            name="슬랙1조",
            order=1,
        )
        cls.user = User.objects.create_user(
            username="slack_user",
            email="slack@example.com",
            password="x",
            signup_source=User.SignupSource.KAKAO,
        )
        profile = ensure_user_profile(cls.user)
        profile.display_name = "슬랙유저"
        profile.real_name = "김슬랙"
        profile.phone = "01012345678"
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.save()
        UserDivisionTeam.objects.create(
            user=cls.user, division=cls.division, is_primary=True
        )

    def test_public_site_base_url_by_env(self):
        with override_settings(ENV="local"):
            self.assertEqual(public_site_base_url(), "http://localhost:8000")
        with override_settings(ENV="dev"):
            self.assertEqual(
                public_site_base_url(), "https://shalom.dev.jcc-seoul.com:8443"
            )
        with override_settings(ENV="production"):
            self.assertEqual(public_site_base_url(), "https://shalom.jcc-seoul.com")

    def test_user_signup_blocks_include_fields_and_link(self):
        blocks = get_user_signup_blocks(self.user)
        text = blocks[0]["text"]["text"]
        self.assertIn("회원가입 알림", text)
        self.assertIn("슬랙유저", text)
        self.assertIn("slack_user", text)
        self.assertIn("slack@example.com", text)
        self.assertIn("01012345678", text)
        button = blocks[2]["elements"][0]
        self.assertEqual(button["text"]["text"], "계정 관리에서 확인")
        self.assertIn(reverse("user_division_account_roles"), button["url"])
        self.assertIn("q=%EA%B9%80%EC%8A%AC%EB%9E%99", button["url"])  # 김슬랙
        self.assertIn("division_code=__all__", button["url"])

    def test_staff_application_blocks_include_fields_and_link(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.user,
            region=self.region,
            division=self.division,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )
        blocks = get_staff_application_blocks(application)
        text = blocks[0]["text"]["text"]
        self.assertIn("수련회 운영진 참가 신청 알림", text)
        self.assertIn("슬랙 수련회", text)
        self.assertIn("슬랙유저", text)
        self.assertIn("조 운영진", text)
        button = blocks[2]["elements"][0]
        self.assertIn(
            reverse("retreat_staff_applications", args=[self.event.id]),
            button["url"],
        )


class SlackClientTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="slack_client_user",
            email="c@example.com",
            password="x",
            signup_source=User.SignupSource.KAKAO,
        )
        ensure_user_profile(self.user)

    @override_settings(ENV="production", SLACK_NOTIFICATIONS_ENABLED=True)
    @patch("utils.slack.client.WebClient")
    def test_send_user_signup_posts_to_signup_channel(self, mock_web_client_cls):
        mock_client = MagicMock()
        mock_web_client_cls.return_value = mock_client
        client = SlackClient(token="xoxb-test")
        client.send_user_signup(self.user)
        mock_client.chat_postMessage.assert_called_once()
        kwargs = mock_client.chat_postMessage.call_args.kwargs
        self.assertEqual(kwargs["channel"], "#500_회원가입_알림")
        self.assertEqual(kwargs["text"], "회원가입 알림")
        self.assertTrue(kwargs["blocks"])

    @override_settings(ENV="dev", SLACK_NOTIFICATIONS_ENABLED=True)
    @patch("utils.slack.client.WebClient")
    def test_send_message_overrides_channel_on_dev(self, mock_web_client_cls):
        mock_client = MagicMock()
        mock_web_client_cls.return_value = mock_client
        client = SlackClient(token="xoxb-test")
        client.send_message(channel="#500_회원가입_알림", text="회원가입 알림")
        kwargs = mock_client.chat_postMessage.call_args.kwargs
        self.assertEqual(kwargs["channel"], "#232_개발팀_dev")

    @override_settings(SLACK_NOTIFICATIONS_ENABLED=False)
    @patch("utils.slack.client.WebClient")
    def test_send_message_skipped_when_disabled(self, mock_web_client_cls):
        mock_client = MagicMock()
        mock_web_client_cls.return_value = mock_client
        client = SlackClient(token="xoxb-test")
        client.send_message(channel="#500_회원가입_알림", text="회원가입 알림")
        mock_client.chat_postMessage.assert_not_called()


class SlackHookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.region, name="훅청년", code="slack_hook_youth", sort_order=97
        )
        cls.event = RetreatEvent.objects.create(
            name="훅 수련회",
            start_date=date(2027, 9, 1),
            end_date=date(2027, 9, 3),
            staff_applications_open=True,
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.region,
            division=cls.division,
            name="훅1조",
            order=1,
        )
        cls.user = User.objects.create_user(
            username="slack_hook_user", password="x", email="hook@example.com"
        )
        UserDivisionTeam.objects.create(
            user=cls.user, division=cls.division, is_primary=True
        )
        profile = ensure_user_profile(cls.user)
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.save()

    @patch("utils.slack.client.SlackClient.send_staff_application")
    def test_staff_form_save_calls_slack(self, mock_send):
        form = RetreatStaffApplicationForm(
            data={
                "region": self.region.id,
                "division": self.division.id,
                "application_track": StaffApplicationTrack.GROUP_LEADERSHIP,
                "group": self.group.id,
                "group_role": RetreatGroupMembership.Role.LEADER,
            },
            event=self.event,
            user=self.user,
            read_only=False,
        )
        self.assertTrue(form.is_valid(), form.errors)
        application = form.save()
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.args[0].id, application.id)

    @patch("utils.slack.client.SlackClient.send_user_signup")
    @patch("users.services.kakao_auth._download_image_bytes", return_value=None)
    def test_kakao_create_calls_slack(self, _mock_download, mock_send):
        from users.services.kakao_auth import create_or_update_kakao_user

        strategy = MagicMock()
        backend = MagicMock()
        backend.name = "kakao"
        result = create_or_update_kakao_user(
            strategy=strategy,
            details={"email": "newslack@example.com", "nickname": "신규"},
            backend=backend,
            uid="slack_new_uid_1",
            user=None,
            response={"kakao_account": {"profile": {"nickname": "신규"}}},
            is_new=True,
        )
        self.assertIsNotNone(result["user"].pk)
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.args[0].id, result["user"].id)
