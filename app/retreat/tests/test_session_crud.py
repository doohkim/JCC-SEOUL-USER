"""출석부(세션) CRUD API 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from retreat.models import (
    RetreatChangeLog,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatSession,
)
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class RetreatSessionApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="rt_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="테스트 수련회",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 3),
        )
        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president", defaults={"name": "회장", "level": 80, "sort_order": 20}
        )
        cls.staff = User.objects.create_user(username="sess_staff", password="x")
        cls.staff.role_level = cls.rl_president
        cls.staff.save()
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.div, is_primary=True
        )
        # staff 이면서 회장단도 겸하는 경우만 출석부 생성 가능.
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.staff,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )
        cls.leader = User.objects.create_user(username="sess_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )

    def setUp(self):
        self.client = APIClient()

    def test_council_can_create_session(self):
        self.client.force_authenticate(self.staff)  # staff + 회장단
        url = reverse("api_retreat_event_sessions", args=[self.event.id])
        r = self.client.post(url, {"name": "1일차 입실"}, format="json")
        self.assertEqual(r.status_code, 201)
        session = RetreatSession.objects.get(name="1일차 입실")
        self.assertEqual(session.created_by_id, self.staff.id)
        self.assertTrue(
            RetreatChangeLog.objects.filter(
                target_type=RetreatChangeLog.TargetType.SESSION,
                target_id=session.id,
                action=RetreatChangeLog.Action.CREATE,
            ).exists()
        )

    def test_leader_cannot_create_session(self):
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_sessions", args=[self.event.id])
        r = self.client.post(url, {"name": "불가"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_create_session_with_closed_status_autofills_closer(self):
        # status=closed 로 만들면 closed_by 가 작성자로 채워지고 closed_at도 자동 기록.
        self.client.force_authenticate(self.staff)
        url = reverse("api_retreat_event_sessions", args=[self.event.id])
        r = self.client.post(
            url,
            {"name": "이미 마감된 출석부", "status": "closed"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        session = RetreatSession.objects.get(name="이미 마감된 출석부")
        self.assertEqual(session.status, RetreatSession.Status.CLOSED)
        self.assertIsNotNone(session.closed_at)
        self.assertEqual(session.closed_by_id, self.staff.id)

    def test_create_session_with_explicit_closed_at(self):
        from django.utils import timezone

        explicit = timezone.now().replace(microsecond=0)
        self.client.force_authenticate(self.staff)
        url = reverse("api_retreat_event_sessions", args=[self.event.id])
        r = self.client.post(
            url,
            {
                "name": "마감 시각 명시",
                "status": "closed",
                "closed_at": explicit.isoformat(),
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        session = RetreatSession.objects.get(name="마감 시각 명시")
        self.assertEqual(session.status, RetreatSession.Status.CLOSED)
        self.assertEqual(
            session.closed_at.replace(microsecond=0), explicit
        )
        self.assertEqual(session.closed_by_id, self.staff.id)

    def test_active_status_clears_closed_at_payload(self):
        # ACTIVE 로 보낼 때는 사용자가 closed_at을 보냈더라도 무시되어야 한다.
        from django.utils import timezone

        self.client.force_authenticate(self.staff)
        url = reverse("api_retreat_event_sessions", args=[self.event.id])
        r = self.client.post(
            url,
            {
                "name": "진행중 강제",
                "status": "active",
                "closed_at": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        session = RetreatSession.objects.get(name="진행중 강제")
        self.assertEqual(session.status, RetreatSession.Status.ACTIVE)
        self.assertIsNone(session.closed_at)
        self.assertIsNone(session.closed_by_id)
