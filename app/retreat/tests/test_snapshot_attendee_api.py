"""마감 출석부 스냅샷 조원 API 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatSession,
    RetreatSessionAttendee,
)
from retreat.services.enrollment import close_session, snapshot_session_enrollments
from users.models import Division, Region, UserDivisionTeam

User = get_user_model()


class SnapshotAttendeeApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.region,
            code="snap_youth",
            name="청년부",
        )
        cls.event = RetreatEvent.objects.create(
            name="스냅샷 API",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.region,
            division=cls.division,
            name="1조",
        )
        cls.active = RetreatSession.objects.create(event=cls.event, name="진행")
        cls.closed = RetreatSession.objects.create(event=cls.event, name="마감")
        snapshot_session_enrollments(cls.active, actor=None)
        snapshot_session_enrollments(cls.closed, actor=None)
        close_session(cls.closed, actor=None)

        cls.leader = User.objects.create_user(username="snap_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.division, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.council = User.objects.create_user(username="snap_council", password="x")
        UserDivisionTeam.objects.create(
            user=cls.council, division=cls.division, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council,
            role=RetreatCouncilMembership.Role.CHAIRPERSON,
        )

        cls.other_event = RetreatEvent.objects.create(
            name="다른 행사",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
        )
        cls.other_group = RetreatGroup.objects.create(
            event=cls.other_event,
            region=cls.region,
            division=cls.division,
            name="타조",
        )

    def setUp(self):
        self.client = APIClient()

    def _add_url(self, session_id=None, group_id=None):
        return reverse(
            "api_retreat_session_group_snapshot_attendees",
            args=[session_id or self.closed.id, group_id or self.group.id],
        )

    def _detail_url(self, enrollment_id: int):
        return reverse(
            "api_retreat_snapshot_attendee_detail",
            args=[enrollment_id],
        )

    def test_admin_can_add_to_closed_session_isolated(self):
        self.client.force_authenticate(self.council)
        before_attendees = RetreatAttendee.objects.count()
        before_active_enroll = RetreatSessionAttendee.objects.filter(
            session=self.active
        ).count()
        before_closed_enroll = RetreatSessionAttendee.objects.filter(
            session=self.closed
        ).count()

        response = self.client.post(
            self._add_url(),
            {"name": "마감전용", "phone": "010-1111-2222"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)

        enrollment = RetreatSessionAttendee.objects.get(name="마감전용")
        self.assertEqual(enrollment.session_id, self.closed.id)
        self.assertEqual(enrollment.source_group_id, self.group.id)
        self.assertIsNone(enrollment.source_attendee_id)
        self.assertEqual(
            RetreatAttendance.objects.get(enrollment=enrollment).status,
            RetreatAttendance.Status.ABSENT,
        )
        self.assertEqual(RetreatAttendee.objects.count(), before_attendees)
        self.assertEqual(
            RetreatSessionAttendee.objects.filter(session=self.active).count(),
            before_active_enroll,
        )
        self.assertEqual(
            RetreatSessionAttendee.objects.filter(session=self.closed).count(),
            before_closed_enroll + 1,
        )

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(self.leader)
        response = self.client.post(
            self._add_url(),
            {"name": "조장시도"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_event_mismatch_rejected(self):
        self.client.force_authenticate(self.council)
        response = self.client.post(
            self._add_url(session_id=self.closed.id, group_id=self.other_group.id),
            {"name": "불일치"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_active_session_rejected(self):
        self.client.force_authenticate(self.council)
        response = self.client.post(
            self._add_url(session_id=self.active.id),
            {"name": "진행중추가"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_can_patch_snapshot_only_row_in_closed_session(self):
        self.client.force_authenticate(self.council)
        create = self.client.post(
            self._add_url(),
            {"name": "수정대상"},
            format="json",
        )
        enrollment_id = create.json()["id"]

        response = self.client.patch(
            self._detail_url(enrollment_id),
            {"name": "수정됨", "memo": "메모", "gender": "female"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        enrollment = RetreatSessionAttendee.objects.get(pk=enrollment_id)
        self.assertEqual(enrollment.name, "수정됨")
        self.assertEqual(enrollment.memo, "메모")
        self.assertEqual(enrollment.gender, "female")
        self.assertEqual(response.json().get("gender"), "female")

    def test_admin_cannot_patch_live_linked_row(self):
        attendee = RetreatAttendee.objects.create(group=self.group, name="라이브")
        enrollment = RetreatSessionAttendee.objects.create(
            session=self.closed,
            source_attendee=attendee,
            source_group=self.group,
            name=attendee.name,
            group_name=self.group.name,
        )
        self.client.force_authenticate(self.council)
        response = self.client.patch(
            self._detail_url(enrollment.id),
            {"name": "불가"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_can_delete_snapshot_only_row_cascades_attendance(self):
        self.client.force_authenticate(self.council)
        create = self.client.post(
            self._add_url(),
            {"name": "삭제대상"},
            format="json",
        )
        enrollment_id = create.json()["id"]
        self.assertTrue(
            RetreatAttendance.objects.filter(enrollment_id=enrollment_id).exists()
        )

        response = self.client.delete(self._detail_url(enrollment_id))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(RetreatSessionAttendee.objects.filter(pk=enrollment_id).exists())
        self.assertFalse(
            RetreatAttendance.objects.filter(enrollment_id=enrollment_id).exists()
        )
