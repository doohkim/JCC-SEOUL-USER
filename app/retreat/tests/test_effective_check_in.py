"""예정 시각 기준 유효 입·퇴실 상태 테스트."""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from retreat.models import RetreatAttendee, RetreatEvent, RetreatGroup
from retreat.services.effective_check_in import effective_status
from users.models import Division, Region


class EffectiveCheckInTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.get(code="seoul")
        division = Division.objects.create(
            region=region, code="effective_youth", name="청년부"
        )
        event = RetreatEvent.objects.create(
            name="유효 상태 테스트",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
        )
        cls.group = RetreatGroup.objects.create(
            event=event, region=region, division=division, name="1조"
        )

    def test_pending_before_expected_check_in(self):
        now = timezone.now()
        attendee = RetreatAttendee.objects.create(
            group=self.group,
            name="입실전",
            expected_check_in_at=now + timedelta(minutes=1),
        )
        self.assertEqual(
            effective_status(attendee, now), RetreatAttendee.CheckInStatus.PENDING
        )

    def test_checked_in_after_expected_check_in_without_database_write(self):
        now = timezone.now()
        attendee = RetreatAttendee.objects.create(
            group=self.group,
            name="입실",
            expected_check_in_at=now - timedelta(minutes=1),
        )
        self.assertEqual(
            effective_status(attendee, now), RetreatAttendee.CheckInStatus.CHECKED_IN
        )
        attendee.refresh_from_db()
        self.assertEqual(
            attendee.check_in_status, RetreatAttendee.CheckInStatus.PENDING
        )

    def test_checked_out_after_expected_check_out(self):
        now = timezone.now()
        attendee = RetreatAttendee.objects.create(
            group=self.group,
            name="퇴실",
            expected_check_in_at=now - timedelta(hours=2),
            expected_check_out_at=now - timedelta(minutes=1),
        )
        self.assertEqual(
            effective_status(attendee, now),
            RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )

    def test_manual_status_overrides_expected_status(self):
        now = timezone.now()
        attendee = RetreatAttendee.objects.create(
            group=self.group,
            name="수동예외",
            expected_check_in_at=now - timedelta(hours=2),
            expected_check_out_at=now - timedelta(minutes=1),
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            check_in_status_manually_set=True,
        )
        self.assertEqual(
            effective_status(attendee, now), RetreatAttendee.CheckInStatus.CHECKED_IN
        )
