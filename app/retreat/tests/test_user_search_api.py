"""수련회 사용자 검색 API."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from retreat.models import RetreatEvent, RetreatGroup, RetreatGroupMembership
from users.models import Division, Region, UserDivisionTeam

User = get_user_model()


class UserSearchApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="us_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="user-search",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )

        cls.leader = User.objects.create_user(username="us_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.target_a = User.objects.create_user(
            username="kakao_4925845288", password="x"
        )
        cls.target_b = User.objects.create_user(
            username="kakao_4812361055", password="x"
        )
        cls.outsider = User.objects.create_user(username="us_outsider", password="x")

    def setUp(self):
        self.client = APIClient()

    def test_outsider_cannot_search(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.get(reverse("api_retreat_user_search"), {"q": "kakao"})
        self.assertEqual(r.status_code, 403)

    def test_leader_can_search_by_partial_username(self):
        self.client.force_authenticate(self.leader)
        r = self.client.get(reverse("api_retreat_user_search"), {"q": "4925"})
        self.assertEqual(r.status_code, 200)
        usernames = [u["username"] for u in r.json()]
        self.assertIn(self.target_a.username, usernames)
        self.assertNotIn(self.target_b.username, usernames)

    def test_blank_query_returns_empty_without_filter(self):
        self.client.force_authenticate(self.leader)
        r = self.client.get(reverse("api_retreat_user_search"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_division_filter_lists_members_without_query(self):
        self.client.force_authenticate(self.leader)
        r = self.client.get(
            reverse("api_retreat_user_search"), {"division": self.div.id}
        )
        self.assertEqual(r.status_code, 200)
        usernames = [u["username"] for u in r.json()]
        self.assertIn(self.leader.username, usernames)
        self.assertNotIn(self.target_a.username, usernames)

    def test_division_filter_with_query_narrows(self):
        UserDivisionTeam.objects.create(
            user=self.target_a, division=self.div, is_primary=False
        )
        self.client.force_authenticate(self.leader)
        r = self.client.get(
            reverse("api_retreat_user_search"),
            {"division": self.div.id, "q": "4925"},
        )
        self.assertEqual(r.status_code, 200)
        usernames = [u["username"] for u in r.json()]
        self.assertEqual(usernames, [self.target_a.username])

    def test_limit_capped(self):
        self.client.force_authenticate(self.leader)
        r = self.client.get(
            reverse("api_retreat_user_search"), {"limit": "999"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertLessEqual(len(r.json()), 30)
