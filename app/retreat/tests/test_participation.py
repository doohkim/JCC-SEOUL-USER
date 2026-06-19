"""집회 단위 참석/불참(participation_status) 테스트."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from retreat.models import (
    Lodging,
    LodgingRoom,
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatSession,
    RetreatSessionAttendee,
)
from retreat.services.auto_check_in import apply_due_auto_transitions
from retreat.services.dashboard import build_realtime_dashboard
from retreat.services.lodging_roster import (
    attendee_lodging_cell_label,
    is_lodging_eligible,
)
from retreat.services.participation import is_participating
from users.models import Division, Region

User = get_user_model()


class ParticipationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="bk_part_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="참석 테스트",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.leader = User.objects.create_user(
            username="part_leader",
            password="x",
        )
        RetreatGroupMembership.objects.create(
            group=cls.group,
            user=cls.leader,
            role=RetreatGroupMembership.Role.LEADER,
        )
        cls.lodging = Lodging.objects.create(
            event=cls.event, name="A동", region=cls.seoul
        )
        cls.room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="101",
            region=cls.seoul,
            division=cls.div,
            capacity=4,
        )
        cls.now = timezone.now()
        cls.participant = RetreatAttendee.objects.create(
            group=cls.group,
            name="참석자",
            expected_check_in_at=cls.now - timedelta(hours=1),
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        cls.absentee = RetreatAttendee.objects.create(
            group=cls.group,
            name="불참자",
            participation_status=RetreatAttendee.ParticipationStatus.ABSENT,
            expected_check_in_at=cls.now - timedelta(hours=1),
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            lodging_room=cls.room,
        )

    def test_is_participating(self):
        self.assertTrue(is_participating(self.participant))
        self.assertFalse(is_participating(self.absentee))

    def test_lodging_ineligible_when_absent(self):
        self.assertFalse(is_lodging_eligible(self.absentee))
        self.assertEqual(attendee_lodging_cell_label(self.absentee), "불참")

    def test_auto_check_in_skips_absent(self):
        result = apply_due_auto_transitions(
            now=self.now, event_id=self.event.id
        )
        self.assertEqual(result["checked_in"], 1)
        self.participant.refresh_from_db()
        self.absentee.refresh_from_db()
        self.assertEqual(
            self.participant.check_in_status,
            RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        self.assertEqual(
            self.absentee.check_in_status,
            RetreatAttendee.CheckInStatus.PENDING,
        )

    def test_dashboard_excludes_absent_from_totals(self):
        data = build_realtime_dashboard(
            self.event, self.leader, staff_view=False
        )
        self.assertEqual(data["grand_total"]["total"], 1)
        self.assertEqual(data["grand_total"]["absent"], 1)

    def test_patch_participation_clears_lodging(self):
        client = APIClient()
        client.force_authenticate(self.leader)
        attending = RetreatAttendee.objects.create(
            group=self.group,
            name="배정자",
            expected_check_in_at=self.now,
            lodging_room=self.room,
        )
        url = f"/api/v1/retreat/attendees/{attending.id}/"
        r = client.patch(
            url,
            {"participation_status": RetreatAttendee.ParticipationStatus.ABSENT},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        attending.refresh_from_db()
        self.assertIsNone(attending.lodging_room_id)
        self.assertEqual(
            attending.participation_status,
            RetreatAttendee.ParticipationStatus.ABSENT,
        )

    def test_bulk_upsert_blocks_present_for_master_absent(self):
        session = RetreatSession.objects.create(
            event=self.event, name="저녁", sequence=1
        )
        enrollment, _ = RetreatSessionAttendee.objects.get_or_create(
            session=session,
            source_attendee=self.absentee,
            defaults={
                "source_group": self.group,
                "name": self.absentee.name,
                "check_in_status": RetreatAttendee.CheckInStatus.CHECKED_IN,
                "group_name": self.group.name,
                "region_id_snapshot": self.seoul.id,
                "region_name": self.seoul.name,
                "division_id_snapshot": self.div.id,
                "division_name": self.div.name,
            },
        )
        client = APIClient()
        client.force_authenticate(self.leader)
        r = client.post(
            "/api/v1/retreat/attendance/bulk-upsert/",
            {
                "session_id": session.id,
                "rows": [{"enrollment_id": enrollment.id, "status": "present"}],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)
