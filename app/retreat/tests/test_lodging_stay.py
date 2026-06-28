"""숙박 상태(lodging_stay_status) resolve·sync·display 테스트."""

from __future__ import annotations

from datetime import date

from django.test import TestCase
from django.utils import timezone

from retreat.models import (
    Lodging,
    LodgingRoom,
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
)
from retreat.services.lodging_stay import (
    lodging_stay_display,
    persist_lodging_stay_status,
    resolve_lodging_stay_status,
    sync_lodging_stay_status,
)
from users.models import Division, Region


class LodgingStayStatusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="stay_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="숙박 상태",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.lodging = Lodging.objects.create(event=cls.event, name="본관")
        cls.room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="101",
            region=cls.seoul,
            division=cls.div,
        )
        cls.now = timezone.now()

    def _attendee(self, **kwargs) -> RetreatAttendee:
        return RetreatAttendee.objects.create(group=self.group, name="테스트", **kwargs)

    def test_resolve_absent(self):
        a = self._attendee(
            participation_status=RetreatAttendee.ParticipationStatus.ABSENT,
            expected_check_in_at=self.now,
            lodging_room=self.room,
        )
        self.assertEqual(
            resolve_lodging_stay_status(a),
            RetreatAttendee.LodgingStayStatus.ABSENT,
        )

    def test_resolve_ended(self):
        a = self._attendee(
            expected_check_in_at=self.now,
            lodging_room=self.room,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        self.assertEqual(
            resolve_lodging_stay_status(a),
            RetreatAttendee.LodgingStayStatus.ENDED,
        )

    def test_resolve_no_stay(self):
        a = self._attendee(check_in_status=RetreatAttendee.CheckInStatus.PENDING)
        self.assertEqual(
            resolve_lodging_stay_status(a),
            RetreatAttendee.LodgingStayStatus.NO_STAY,
        )

    def test_resolve_active(self):
        a = self._attendee(
            expected_check_in_at=self.now,
            lodging_room=self.room,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        self.assertEqual(
            resolve_lodging_stay_status(a),
            RetreatAttendee.LodgingStayStatus.ACTIVE,
        )

    def test_resolve_unassigned(self):
        a = self._attendee(
            expected_check_in_at=self.now,
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        self.assertEqual(
            resolve_lodging_stay_status(a),
            RetreatAttendee.LodgingStayStatus.UNASSIGNED,
        )

    def test_sync_returns_false_when_unchanged(self):
        a = self._attendee(
            expected_check_in_at=self.now,
            lodging_stay_status=RetreatAttendee.LodgingStayStatus.UNASSIGNED,
        )
        self.assertFalse(sync_lodging_stay_status(a))

    def test_sync_updates_status(self):
        a = self._attendee(
            expected_check_in_at=self.now,
            lodging_room=self.room,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        self.assertTrue(sync_lodging_stay_status(a))
        self.assertEqual(a.lodging_stay_status, RetreatAttendee.LodgingStayStatus.ACTIVE)

    def test_display_active_shows_room(self):
        a = self._attendee(
            expected_check_in_at=self.now,
            lodging_room=self.room,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            lodging_stay_status=RetreatAttendee.LodgingStayStatus.ACTIVE,
        )
        a.name = "홍길동"
        self.assertEqual(lodging_stay_display(a), "본관 101")

    def test_display_no_stay(self):
        a = self._attendee(
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            lodging_stay_status=RetreatAttendee.LodgingStayStatus.NO_STAY,
        )
        self.assertEqual(lodging_stay_display(a), "입실 예정 없음")

    def test_display_ended_without_room_name(self):
        a = self._attendee(
            expected_check_in_at=self.now,
            lodging_room=self.room,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
            lodging_stay_status=RetreatAttendee.LodgingStayStatus.ENDED,
        )
        self.assertEqual(lodging_stay_display(a), "숙박 종료")

    def test_persist_writes_to_db(self):
        a = self._attendee(
            expected_check_in_at=self.now,
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        self.assertTrue(persist_lodging_stay_status(a))
        a.refresh_from_db()
        self.assertEqual(
            a.lodging_stay_status, RetreatAttendee.LodgingStayStatus.UNASSIGNED
        )
