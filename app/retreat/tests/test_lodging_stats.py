"""숙소 summary 집계 테스트."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from retreat.models import (
    Lodging,
    LodgingRoom,
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
)
from retreat.services.lodging_stay import persist_lodging_stay_status
from retreat.services.lodging_stats import build_lodging_page_summary
from users.models import Division, Region


class LodgingStatsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="lodging_stats_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="숙소 집계",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.lodging_a = Lodging.objects.create(event=cls.event, name="사랑방숙소")
        cls.lodging_b = Lodging.objects.create(event=cls.event, name="호텔")
        cls.room_a = LodgingRoom.objects.create(
            lodging=cls.lodging_a, number="101", capacity=20
        )
        cls.room_b1 = LodgingRoom.objects.create(
            lodging=cls.lodging_b, number="201", capacity=20
        )
        cls.room_b2 = LodgingRoom.objects.create(
            lodging=cls.lodging_b, number="202", capacity=20
        )
        cls.room_unlimited = LodgingRoom.objects.create(
            lodging=cls.lodging_b, number="203", capacity=0
        )
        cls.now = timezone.make_aware(datetime(2026, 7, 1, 18, 0, 0))

    def _attendee(self, name, *, room=None, status=None, expected_in=None):
        status = status or RetreatAttendee.CheckInStatus.PENDING
        kwargs = {
            "group": self.group,
            "name": name,
            "check_in_status": status,
        }
        if expected_in is not None:
            kwargs["expected_check_in_at"] = expected_in
        if room is not None:
            kwargs["lodging_room"] = room
        attendee = RetreatAttendee.objects.create(**kwargs)
        persist_lodging_stay_status(attendee)
        return attendee

    def test_facility_counts(self):
        summary = build_lodging_page_summary(self.event)
        f = summary.facility
        self.assertEqual(f.lodging_count, 2)
        self.assertEqual(f.room_count, 4)
        self.assertEqual(f.capacity_finite_total, 60)

    def test_eligible_excludes_checked_out_and_no_expected_in(self):
        self._attendee("배정대상", room=self.room_a, expected_in=self.now)
        self._attendee("예상없음", room=self.room_b1)
        self._attendee(
            "퇴실자",
            room=self.room_b2,
            expected_in=self.now,
            status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        self._attendee("미배정", expected_in=self.now + timedelta(hours=2))

        f = build_lodging_page_summary(self.event).facility
        self.assertEqual(f.assigned_active, 1)
        self.assertEqual(f.unassigned_eligible, 1)
        self.assertAlmostEqual(f.assignment_rate_pct, round(1 / 60 * 100, 1))

    def test_checked_out_in_room_not_counted_for_rooms_remaining(self):
        self._attendee(
            "퇴실잔존",
            room=self.room_a,
            expected_in=self.now,
            status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        f = build_lodging_page_summary(self.event).facility
        self.assertEqual(f.assigned_active, 0)
        self.assertEqual(f.rooms_remaining, 4)

    def test_assigned_pending_only_active_assigned(self):
        self._attendee(
            "입실",
            room=self.room_a,
            expected_in=self.now,
            status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        self._attendee(
            "입실전",
            room=self.room_b1,
            expected_in=self.now + timedelta(hours=2),
            status=RetreatAttendee.CheckInStatus.PENDING,
        )
        self._attendee(
            "퇴실배정",
            room=self.room_b2,
            expected_in=self.now,
            status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )

        f = build_lodging_page_summary(self.event).facility
        self.assertEqual(f.assigned_pending, 1)
        self.assertEqual(f.assigned_active, 2)
