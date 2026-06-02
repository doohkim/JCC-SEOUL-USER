"""수련회 회장단 권한 회귀 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from retreat.models import (
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatSession,
)
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class _CouncilFixture:
    @classmethod
    def setup_fixture(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="council_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="회장단 테스트",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )

        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president",
            defaults={"name": "회장", "level": 80, "sort_order": 20},
        )

        cls.staff = User.objects.create_user(username="cl_staff", password="x")
        cls.staff.role_level = cls.rl_president
        cls.staff.save()
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.div, is_primary=True
        )

        cls.council = User.objects.create_user(username="cl_council", password="x")
        UserDivisionTeam.objects.create(
            user=cls.council, division=cls.div, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council,
            role=RetreatCouncilMembership.Role.CHAIRPERSON,
        )

        cls.leader = User.objects.create_user(username="cl_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)


class CouncilSessionGateApiTests(APITestCase, _CouncilFixture):
    @classmethod
    def setUpTestData(cls):
        cls.setup_fixture()

    def setUp(self):
        self.client = APIClient()

    def test_council_can_create_session(self):
        self.client.force_authenticate(self.council)
        url = reverse("api_retreat_event_sessions", args=[self.event.id])
        r = self.client.post(url, {"name": "1일차"}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_staff_without_council_cannot_create_session(self):
        self.client.force_authenticate(self.staff)
        url = reverse("api_retreat_event_sessions", args=[self.event.id])
        r = self.client.post(url, {"name": "차단"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_leader_cannot_create_session(self):
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_sessions", args=[self.event.id])
        r = self.client.post(url, {"name": "차단"}, format="json")
        self.assertEqual(r.status_code, 403)


class CouncilManagementApiTests(APITestCase, _CouncilFixture):
    @classmethod
    def setUpTestData(cls):
        cls.setup_fixture()
        cls.extra = User.objects.create_user(username="cl_extra", password="x")

    def setUp(self):
        self.client = APIClient()

    def test_council_can_add_member(self):
        self.client.force_authenticate(self.council)
        url = reverse("api_retreat_event_council", args=[self.event.id])
        r = self.client.post(
            url,
            {"username": self.extra.username, "role": "member"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(
            RetreatCouncilMembership.objects.filter(
                event=self.event, user=self.extra
            ).exists()
        )

    def test_staff_without_council_cannot_add_member(self):
        self.client.force_authenticate(self.staff)
        url = reverse("api_retreat_event_council", args=[self.event.id])
        r = self.client.post(url, {"username": self.extra.username}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_staff_can_view_council_list(self):
        self.client.force_authenticate(self.staff)
        url = reverse("api_retreat_event_council", args=[self.event.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)


class CouncilPageAccessTests(TestCase, _CouncilFixture):
    @classmethod
    def setUpTestData(cls):
        cls.setup_fixture()
        cls.stranger = User.objects.create_user(username="cl_stranger", password="x")
        UserDivisionTeam.objects.create(
            user=cls.stranger, division=cls.div, is_primary=True
        )

    def setUp(self):
        self.client = Client()

    def test_council_page_ok_for_council(self):
        self.client.force_login(self.council)
        r = self.client.get(reverse("retreat_council", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)

    def test_council_page_ok_for_staff(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("retreat_council", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)

    def test_council_page_forbidden_for_stranger(self):
        self.client.force_login(self.stranger)
        r = self.client.get(reverse("retreat_council", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)

    def test_council_page_forbidden_for_leader_only(self):
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_council", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)
