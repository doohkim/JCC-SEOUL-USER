from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatSession,
)
from retreat.services.enrollment import close_session, snapshot_session_enrollments
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class ClosedSessionVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.region,
            code="closed_youth",
            name="청년부",
        )
        cls.event = RetreatEvent.objects.create(
            name="마감 테스트",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.region,
            division=cls.division,
            name="1조",
        )
        cls.attendee = RetreatAttendee.objects.create(group=cls.group, name="조원")
        cls.active = RetreatSession.objects.create(event=cls.event, name="진행")
        cls.closed = RetreatSession.objects.create(event=cls.event, name="마감")

        cls.leader = User.objects.create_user(username="closed_leader", password="x")
        UserDivisionTeam.objects.create(user=cls.leader, division=cls.division, is_primary=True)
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.council = User.objects.create_user(username="closed_council", password="x")
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

        role, _ = RoleLevel.objects.get_or_create(
            code="pastor",
            defaults={"name": "목사", "level": 80, "sort_order": 1},
        )
        cls.pastor = User.objects.create_user(username="closed_pastor", password="x")
        cls.pastor.role_level = role
        cls.pastor.save(update_fields=["role_level"])

        snapshot_session_enrollments(cls.active, actor=cls.council)
        snapshot_session_enrollments(cls.closed, actor=cls.council)
        close_session(cls.closed, actor=cls.council)

    def setUp(self):
        self.client = APIClient()

    def _sessions_url(self):
        return reverse("api_retreat_event_sessions", args=[self.event.id])

    def test_leader_does_not_see_closed_session(self):
        self.client.force_authenticate(self.leader)
        response = self.client.get(self._sessions_url())
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.json()}
        self.assertIn(self.active.id, ids)
        self.assertNotIn(self.closed.id, ids)

    def test_council_sees_and_reopens_closed_session(self):
        self.client.force_authenticate(self.council)
        response = self.client.get(self._sessions_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.closed.id, {row["id"] for row in response.json()})

        reopen_url = reverse(
            "api_retreat_session_reopen",
            args=[self.event.id, self.closed.id],
        )
        self.assertEqual(self.client.post(reopen_url).status_code, 200)
        self.closed.refresh_from_db()
        self.assertEqual(self.closed.status, RetreatSession.Status.ACTIVE)

    def test_pastor_without_staff_cannot_list_sessions(self):
        self.client.force_authenticate(self.pastor)
        response = self.client.get(self._sessions_url())
        self.assertEqual(response.status_code, 403)

    def test_closed_session_bulk_upsert_forbidden(self):
        self.client.force_authenticate(self.council)
        enrollment = self.closed.enrollments.get()
        response = self.client.post(
            reverse("api_retreat_attendance_bulk_upsert"),
            {
                "session_id": self.closed.id,
                "rows": [{"enrollment_id": enrollment.id, "status": "present"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
