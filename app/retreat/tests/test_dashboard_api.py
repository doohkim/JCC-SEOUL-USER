"""대시보드·결과 API 집계 테스트."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
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

    def test_dashboard_realtime_counts(self):
        # 입실 시각이 지나고 퇴실 시각은 미설정 → 현재 입실 상태로 집계.
        self.attendee.expected_check_in_at = timezone.now() - timedelta(minutes=10)
        self.attendee.save(update_fields=["expected_check_in_at"])
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["by_group"]), 1)
        self.assertEqual(data["by_group"][0]["checked_in"], 1)
        self.assertEqual(data["by_group"][0]["attended"], 1)
        self.assertEqual(data["grand_total"]["attended"], 1)
        self.assertEqual(data["grand_total"]["checked_in"], 1)
        # 1시간 단위 추이에 입실 1건 집계.
        self.assertEqual(len(data["hourly"]), 1)
        self.assertEqual(data["hourly"][0]["checked_in"], 1)

    def test_dashboard_status_is_time_based(self):
        """저장된 check_in_status 와 무관하게 입실/퇴실 시각으로 상태를 계산한다."""
        now = timezone.now()
        # 입실 시각이 미래 → 저장 상태가 입실이어도 입실전으로 집계.
        self.attendee.check_in_status = RetreatAttendee.CheckInStatus.CHECKED_IN
        self.attendee.expected_check_in_at = now + timedelta(hours=1)
        self.attendee.save(
            update_fields=["check_in_status", "expected_check_in_at"]
        )
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["grand_total"]["pending"], 1)
        self.assertEqual(data["grand_total"]["checked_in"], 0)

        # 퇴실 시각까지 지나면 퇴실로 집계되며 참석(입실+퇴실)에는 포함.
        self.attendee.expected_check_in_at = now - timedelta(hours=2)
        self.attendee.expected_check_out_at = now - timedelta(minutes=5)
        self.attendee.save(
            update_fields=["expected_check_in_at", "expected_check_out_at"]
        )
        data = self.client.get(url).json()
        self.assertEqual(data["grand_total"]["checked_out"], 1)
        self.assertEqual(data["grand_total"]["checked_in"], 0)
        self.assertEqual(data["grand_total"]["attended"], 1)
        # 시각이 전혀 없으면 입실전.
        self.attendee.expected_check_in_at = None
        self.attendee.expected_check_out_at = None
        self.attendee.save(
            update_fields=["expected_check_in_at", "expected_check_out_at"]
        )
        data = self.client.get(url).json()
        self.assertEqual(data["grand_total"]["pending"], 1)
        self.assertEqual(data["grand_total"]["attended"], 0)

    def test_dashboard_persists_due_transitions(self):
        """대시보드 조회 시 입실 시각이 지난 입실전 조원을 DB에 입실로 저장한다."""
        now = timezone.now()
        self.attendee.check_in_status = RetreatAttendee.CheckInStatus.PENDING
        self.attendee.expected_check_in_at = now - timedelta(hours=1)
        self.attendee.save(
            update_fields=["check_in_status", "expected_check_in_at"]
        )
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.attendee.refresh_from_db()
        self.assertEqual(
            self.attendee.check_in_status, RetreatAttendee.CheckInStatus.CHECKED_IN
        )
        self.assertIsNotNone(self.attendee.checked_in_at)

    def test_results_grand_total(self):
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_results", args=[self.event.id])
        r = self.client.get(url, {"session_id": self.session.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["grand_total"], 1)

    def test_results_analytics_matrix(self):
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_results_analytics", args=[self.event.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["groups"]), 1)
        self.assertEqual(len(data["sessions"]), 1)
        sess = data["sessions"][0]
        self.assertEqual(sess["total_present"], 1)
        self.assertEqual(sess["total_registered"], 1)
        gid = str(self.group.id)
        self.assertEqual(sess["groups"][gid]["present"], 1)
        self.assertEqual(sess["groups"][gid]["registered"], 1)
