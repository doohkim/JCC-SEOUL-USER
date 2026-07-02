"""집회 운영진 배정 규칙 B — 집회운영 1 + 조 1."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from retreat.models import (
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
from users.models import Division, Region, UserDivisionTeam

User = get_user_model()


class StaffRosterRulesApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="sr_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="staff-roster-rules",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.group_a = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
            order=1,
        )
        cls.group_b = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="2조",
            order=2,
        )
        cls.admin = User.objects.create_user(username="sr_admin", password="x")
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.admin,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )
        cls.target = User.objects.create_user(username="sr_target", password="x")
        UserDivisionTeam.objects.create(
            user=cls.target, division=cls.div, is_primary=True
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_second_group_in_same_event_rejected(self):
        url_a = reverse("api_retreat_group_memberships", args=[self.group_a.id])
        r1 = self.client.post(
            url_a,
            {"user_id": self.target.id, "role": "leader"},
            format="json",
        )
        self.assertEqual(r1.status_code, 201, r1.content)
        url_b = reverse("api_retreat_group_memberships", args=[self.group_b.id])
        r2 = self.client.post(
            url_b,
            {"user_id": self.target.id, "role": "leader"},
            format="json",
        )
        self.assertEqual(r2.status_code, 400)
        self.assertIn("다른 조", str(r2.json()))

    def test_council_plus_one_group_allowed(self):
        council_url = reverse("api_retreat_event_council", args=[self.event.id])
        r1 = self.client.post(
            council_url,
            {
                "user_id": self.target.id,
                "role": RetreatCouncilMembership.Role.DIVISION_OBSERVER,
                "division": self.div.id,
            },
            format="json",
        )
        self.assertEqual(r1.status_code, 201, r1.content)
        group_url = reverse("api_retreat_group_memberships", args=[self.group_a.id])
        r2 = self.client.post(
            group_url,
            {"user_id": self.target.id, "role": "leader"},
            format="json",
        )
        self.assertEqual(r2.status_code, 201, r2.content)

    def test_second_council_role_update_allowed(self):
        council_url = reverse("api_retreat_event_council", args=[self.event.id])
        r1 = self.client.post(
            council_url,
            {
                "user_id": self.target.id,
                "role": RetreatCouncilMembership.Role.EVENT_OBSERVER,
            },
            format="json",
        )
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self.client.post(
            council_url,
            {
                "user_id": self.target.id,
                "role": RetreatCouncilMembership.Role.PICKUP_OBSERVER,
            },
            format="json",
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        membership = RetreatCouncilMembership.objects.get(
            event=self.event, user=self.target
        )
        self.assertEqual(membership.role, RetreatCouncilMembership.Role.PICKUP_OBSERVER)
