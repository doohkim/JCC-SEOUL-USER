"""예상 시각 기반 자동 입·퇴실 전환 테스트."""

from __future__ import annotations

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from retreat.models import RetreatAttendee, RetreatEvent, RetreatGroup
from retreat.services.auto_check_in import apply_due_auto_transitions
from users.models import Division, Region


class AutoCheckInTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="auto_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="자동 입실 테스트",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event, region=cls.seoul, division=cls.div, name="1조"
        )

    def test_pending_past_expected_in_becomes_checked_in(self):
        now = timezone.now()
        a = RetreatAttendee.objects.create(
            group=self.group,
            name="입실대상",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            expected_check_in_at=now - timedelta(minutes=10),
        )
        result = apply_due_auto_transitions(now=now)
        a.refresh_from_db()
        self.assertEqual(a.check_in_status, RetreatAttendee.CheckInStatus.CHECKED_IN)
        self.assertIsNotNone(a.checked_in_at)
        self.assertEqual(result["checked_in"], 1)

    def test_future_expected_in_not_changed(self):
        now = timezone.now()
        a = RetreatAttendee.objects.create(
            group=self.group,
            name="미래대상",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            expected_check_in_at=now + timedelta(minutes=30),
        )
        apply_due_auto_transitions(now=now)
        a.refresh_from_db()
        self.assertEqual(a.check_in_status, RetreatAttendee.CheckInStatus.PENDING)
        self.assertIsNone(a.checked_in_at)

    def test_checked_in_past_expected_out_becomes_checked_out(self):
        now = timezone.now()
        a = RetreatAttendee.objects.create(
            group=self.group,
            name="퇴실대상",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            expected_check_out_at=now - timedelta(minutes=5),
        )
        result = apply_due_auto_transitions(now=now)
        a.refresh_from_db()
        self.assertEqual(a.check_in_status, RetreatAttendee.CheckInStatus.CHECKED_OUT)
        self.assertIsNotNone(a.checked_out_at)
        self.assertEqual(result["checked_out"], 1)

    def test_pending_past_both_jumps_to_checked_out(self):
        now = timezone.now()
        a = RetreatAttendee.objects.create(
            group=self.group,
            name="둘다경과",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            expected_check_in_at=now - timedelta(hours=2),
            expected_check_out_at=now - timedelta(hours=1),
        )
        apply_due_auto_transitions(now=now)
        a.refresh_from_db()
        self.assertEqual(a.check_in_status, RetreatAttendee.CheckInStatus.CHECKED_OUT)
        self.assertIsNotNone(a.checked_in_at)
        self.assertIsNotNone(a.checked_out_at)

    def test_no_expected_time_not_changed(self):
        now = timezone.now()
        a = RetreatAttendee.objects.create(
            group=self.group,
            name="예상없음",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        apply_due_auto_transitions(now=now)
        a.refresh_from_db()
        self.assertEqual(a.check_in_status, RetreatAttendee.CheckInStatus.PENDING)

    def test_event_id_scopes_transitions(self):
        now = timezone.now()
        other_event = RetreatEvent.objects.create(
            name="다른 집회",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
        )
        other_group = RetreatGroup.objects.create(
            event=other_event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        target = RetreatAttendee.objects.create(
            group=self.group,
            name="대상",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            expected_check_in_at=now - timedelta(minutes=5),
        )
        other = RetreatAttendee.objects.create(
            group=other_group,
            name="다른집회",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            expected_check_in_at=now - timedelta(minutes=5),
        )
        result = apply_due_auto_transitions(now=now, event_id=self.event.id)
        target.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(
            target.check_in_status, RetreatAttendee.CheckInStatus.CHECKED_IN
        )
        self.assertEqual(other.check_in_status, RetreatAttendee.CheckInStatus.PENDING)
        self.assertEqual(result["checked_in"], 1)
