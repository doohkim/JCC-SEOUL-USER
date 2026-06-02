"""대시보드·결과 API 집계 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from retreat.models import (
    RetreatAttendee,
    RetreatAttendance,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatSession,
    RetreatSessionAttendee,
)
from users.models import Division, Region, UserDivisionTeam

User = get_user_model()


class RetreatDashboardApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="dash_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="대시보드 테스트",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 2),
        )
        cls.session = RetreatSession.objects.create(
            event=cls.event, name="입실", sequence=1
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.attendee = RetreatAttendee.objects.create(group=cls.group, name="홍길동")
        cls.enrollment = RetreatSessionAttendee.objects.create(
            session=cls.session,
            source_attendee=cls.attendee,
            source_group=cls.group,
            name=cls.attendee.name,
            phone=cls.attendee.phone,
            gender=cls.attendee.gender,
            check_in_status=cls.attendee.check_in_status,
            group_name=cls.group.name,
            region_id_snapshot=cls.group.region_id,
            region_name=cls.group.region.name,
            division_id_snapshot=cls.group.division_id,
            division_name=cls.group.division.name,
        )
        RetreatAttendance.objects.create(
            enrollment=cls.enrollment,
            status=RetreatAttendance.Status.PRESENT,
        )
        cls.leader = User.objects.create_user(username="dash_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

    def setUp(self):
        self.client = APIClient()

    def test_dashboard_counts_present(self):
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        r = self.client.get(url, {"session_id": self.session.id})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["by_group"]), 1)
        self.assertEqual(data["by_group"][0]["present"], 1)
        self.assertEqual(data["grand_total"]["entered"], 1)

    def test_results_grand_total(self):
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_results", args=[self.event.id])
        r = self.client.get(url, {"session_id": self.session.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["grand_total"], 1)
