"""조원 입·퇴실 시각 자동 기록 API 테스트."""

from __future__ import annotations

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from retreat.models import RetreatAttendee, RetreatEvent, RetreatGroup, RetreatGroupMembership
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class CheckInStampApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.region, code="stamp_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="시각 테스트",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.region,
            division=cls.division,
            name="1조",
        )
        cls.leader = User.objects.create_user(username="stamp_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.division, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president", defaults={"name": "회장", "level": 80, "sort_order": 20}
        )
        cls.staff = User.objects.create_user(username="stamp_staff", password="x")
        cls.staff.role_level = cls.rl_president
        cls.staff.save()
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.division, is_primary=True
        )

        cls.attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="시각대상",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )

    def setUp(self):
        self.client = APIClient()

    def _detail_url(self, attendee_id=None):
        return reverse(
            "api_retreat_attendee_detail",
            args=[attendee_id or self.attendee.id],
        )

    def test_toggle_check_out_sets_checked_out_at(self):
        self.client.force_login(self.leader)
        before = timezone.now()
        response = self.client.patch(
            self._detail_url(),
            {"check_in_status": RetreatAttendee.CheckInStatus.CHECKED_OUT},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.attendee.refresh_from_db()
        self.assertEqual(
            self.attendee.check_in_status, RetreatAttendee.CheckInStatus.CHECKED_OUT
        )
        self.assertIsNotNone(self.attendee.checked_out_at)
        self.assertGreaterEqual(self.attendee.checked_out_at, before)

    def test_leader_cannot_set_timestamp_directly(self):
        self.client.force_login(self.leader)
        manual = timezone.now().isoformat()
        response = self.client.patch(
            self._detail_url(),
            {"checked_in_at": manual},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.attendee.refresh_from_db()
        self.assertIsNone(self.attendee.checked_in_at)

    def test_staff_can_set_timestamp_directly(self):
        self.client.force_login(self.staff)
        manual = timezone.make_aware(datetime(2026, 6, 2, 14, 30, 0))
        response = self.client.patch(
            self._detail_url(),
            {"checked_in_at": manual.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.attendee.refresh_from_db()
        self.assertIsNotNone(self.attendee.checked_in_at)
        self.assertEqual(
            self.attendee.checked_in_at.replace(microsecond=0),
            manual.replace(microsecond=0),
        )

    def test_new_attendee_defaults_to_pending_without_timestamps(self):
        """조원 추가 시 status·시각을 안 보내면 입실전 + 시각 미기록."""
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("api_retreat_group_attendees", args=[self.group.id]),
            {"name": "새조원"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        new_id = response.json()["id"]
        new = RetreatAttendee.objects.get(pk=new_id)
        self.assertEqual(new.check_in_status, RetreatAttendee.CheckInStatus.PENDING)
        self.assertIsNone(new.checked_in_at)
        self.assertIsNone(new.checked_out_at)

    def test_pending_to_check_in_records_checked_in_at(self):
        """입실전 조원이 입실 토글 시 checked_in_at 자동 기록."""
        pending = RetreatAttendee.objects.create(
            group=self.group,
            name="대기조원",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        self.client.force_login(self.leader)
        before = timezone.now()
        response = self.client.patch(
            self._detail_url(pending.id),
            {"check_in_status": RetreatAttendee.CheckInStatus.CHECKED_IN},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        pending.refresh_from_db()
        self.assertEqual(
            pending.check_in_status, RetreatAttendee.CheckInStatus.CHECKED_IN
        )
        self.assertIsNotNone(pending.checked_in_at)
        self.assertGreaterEqual(pending.checked_in_at, before)
