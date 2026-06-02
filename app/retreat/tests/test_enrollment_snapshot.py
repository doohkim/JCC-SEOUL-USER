from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
    RetreatSession,
    RetreatSessionAttendee,
)
from retreat.services.enrollment import (
    close_session,
    enroll_attendee_into_active_sessions,
    snapshot_session_enrollments,
)
from users.models import Division, Region

User = get_user_model()


class RetreatEnrollmentSnapshotTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.region,
            code="snapshot_youth",
            name="청년부",
        )
        cls.event = RetreatEvent.objects.create(
            name="스냅샷 테스트",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.region,
            division=cls.division,
            name="1조",
        )
        cls.actor = User.objects.create_user(username="snapshot_actor", password="x")

    def test_session_creation_snapshots_current_attendees(self):
        attendee = RetreatAttendee.objects.create(group=self.group, name="처음")
        session = RetreatSession.objects.create(event=self.event, name="저녁")

        snapshot_session_enrollments(session, actor=self.actor)

        enrollment = RetreatSessionAttendee.objects.get(session=session)
        self.assertEqual(enrollment.source_attendee, attendee)
        self.assertEqual(enrollment.name, "처음")

        attendee.name = "수정됨"
        attendee.save(update_fields=["name"])
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.name, "처음")

    def test_new_attendee_joins_active_sessions_as_absent_only(self):
        active = RetreatSession.objects.create(event=self.event, name="진행중")
        closed = RetreatSession.objects.create(event=self.event, name="마감")
        close_session(closed, actor=self.actor)

        attendee = RetreatAttendee.objects.create(group=self.group, name="늦게추가")
        enrollments = enroll_attendee_into_active_sessions(attendee, actor=self.actor)

        self.assertEqual([e.session_id for e in enrollments], [active.id])
        enrollment = enrollments[0]
        self.assertTrue(
            RetreatAttendance.objects.filter(
                enrollment=enrollment,
                status=RetreatAttendance.Status.ABSENT,
            ).exists()
        )
        self.assertFalse(
            RetreatSessionAttendee.objects.filter(
                session=closed,
                source_attendee=attendee,
            ).exists()
        )

    def test_deleting_attendee_preserves_snapshot_and_attendance(self):
        attendee = RetreatAttendee.objects.create(
            group=self.group,
            name="보존",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        session = RetreatSession.objects.create(event=self.event, name="아침")
        snapshot_session_enrollments(session, actor=self.actor)
        enrollment = RetreatSessionAttendee.objects.get(session=session)
        RetreatAttendance.objects.create(
            enrollment=enrollment,
            status=RetreatAttendance.Status.PRESENT,
        )

        attendee.delete()
        enrollment.refresh_from_db()

        self.assertIsNone(enrollment.source_attendee_id)
        self.assertEqual(enrollment.name, "보존")
        self.assertEqual(enrollment.attendance.status, RetreatAttendance.Status.PRESENT)
