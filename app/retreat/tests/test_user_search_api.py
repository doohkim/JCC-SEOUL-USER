"""수련회 사용자 검색 API."""

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
from users.mixins import ensure_user_profile
from users.models import (
    Division,
    PastoralDivisionAssignment,
    Region,
    RoleLevel,
    UserDivisionTeam,
)

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
        profile_a = ensure_user_profile(cls.target_a)
        profile_a.display_name = "카카오닉A"
        profile_a.real_name = "김도오"
        profile_a.phone = "010-1234-6804"
        profile_a.gender = profile_a.Gender.MALE
        profile_a.save(
            update_fields=[
                "display_name",
                "real_name",
                "phone",
                "gender",
                "updated_at",
            ]
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
        matched = next(u for u in r.json() if u["username"] == self.target_a.username)
        self.assertEqual(matched["name"], "김도오-6804")
        self.assertEqual(matched["real_name"], "김도오")
        self.assertEqual(matched["gender"], "male")
        self.assertEqual(matched["phone"], "010-1234-6804")

    def test_leader_can_search_by_real_name_and_phone_suffix(self):
        UserDivisionTeam.objects.create(
            user=self.target_a, division=self.div, is_primary=False
        )
        self.client.force_authenticate(self.leader)
        for q in ("김도오", "6804"):
            with self.subTest(q=q):
                r = self.client.get(
                    reverse("api_retreat_user_search"),
                    {"division": self.div.id, "q": q},
                )
                self.assertEqual(r.status_code, 200)
                usernames = [u["username"] for u in r.json()]
                self.assertEqual(usernames, [self.target_a.username])
                self.assertEqual(r.json()[0]["name"], "김도오-6804")

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
        r = self.client.get(reverse("api_retreat_user_search"), {"limit": "999"})
        self.assertEqual(r.status_code, 200)
        self.assertLessEqual(len(r.json()), 30)

    def test_multiple_division_filter_includes_extra_scope_members(self):
        div_extra = Division.objects.create(
            region=self.seoul, code="us_univ", name="대학부"
        )
        user_extra = User.objects.create_user(username="us_extra_div", password="x")
        UserDivisionTeam.objects.create(
            user=user_extra, division=div_extra, is_primary=True
        )
        self.client.force_authenticate(self.leader)
        r = self.client.get(
            reverse("api_retreat_user_search"),
            {"division": [self.div.id, div_extra.id]},
        )
        self.assertEqual(r.status_code, 200)
        usernames = [u["username"] for u in r.json()]
        self.assertIn(self.leader.username, usernames)
        self.assertIn(user_extra.username, usernames)

        r_single = self.client.get(
            reverse("api_retreat_user_search"), {"division": self.div.id}
        )
        usernames_single = [u["username"] for u in r_single.json()]
        self.assertNotIn(user_extra.username, usernames_single)

    def test_staff_pool_council_search_includes_group_staff(self):
        self.client.force_authenticate(self.leader)
        r = self.client.get(
            reverse("api_retreat_user_search"),
            {
                "event_id": self.event.id,
                "staff_pool": "1",
                "staff_pool_kind": "council",
                "q": "us_leader",
            },
        )
        self.assertEqual(r.status_code, 200)
        usernames = [u["username"] for u in r.json()]
        self.assertIn(self.leader.username, usernames)

    def test_staff_pool_council_search_excludes_existing_council(self):
        RetreatCouncilMembership.objects.create(event=self.event, user=self.leader)
        self.client.force_authenticate(self.leader)
        r = self.client.get(
            reverse("api_retreat_user_search"),
            {
                "event_id": self.event.id,
                "staff_pool": "1",
                "staff_pool_kind": "council",
                "q": "us_leader",
            },
        )
        self.assertEqual(r.status_code, 200)
        usernames = [u["username"] for u in r.json()]
        self.assertNotIn(self.leader.username, usernames)

    def test_staff_pool_group_search_excludes_group_staff(self):
        self.client.force_authenticate(self.leader)
        r = self.client.get(
            reverse("api_retreat_user_search"),
            {
                "event_id": self.event.id,
                "staff_pool": "1",
                "staff_pool_kind": "group",
                "q": "us_leader",
            },
        )
        self.assertEqual(r.status_code, 200)
        usernames = [u["username"] for u in r.json()]
        self.assertNotIn(self.leader.username, usernames)

    def test_staff_pool_includes_pastoral_assigned_division_and_affiliations(self):
        div_univ = Division.objects.create(
            region=self.seoul, code="us_staff_univ", name="대학부"
        )
        RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=div_univ,
            name="2조",
        )

        pastoral_level, _ = RoleLevel.objects.get_or_create(
            code="evangelist",
            defaults={"name": "전도사", "level": 80, "sort_order": 90},
        )
        pastoral_user = User.objects.create_user(
            username="us_pastoral_multi", password="x"
        )
        pastoral_user.role_level = pastoral_level
        pastoral_user.save(update_fields=["role_level"])

        # 주 소속은 집회 부서와 무관하게 두고, 목회 담당부서로만 집회 부서를 연결한다.
        div_outside = Division.objects.create(
            region=self.seoul, code="us_staff_outside", name="외부부서"
        )
        UserDivisionTeam.objects.create(
            user=pastoral_user, division=div_outside, is_primary=True
        )
        PastoralDivisionAssignment.objects.create(
            user=pastoral_user, division=self.div, is_primary=True
        )
        PastoralDivisionAssignment.objects.create(
            user=pastoral_user, division=div_univ, is_primary=False
        )
        profile = ensure_user_profile(pastoral_user)
        profile.onboarding_status = profile.OnboardingStatus.APPROVED
        profile.save(update_fields=["onboarding_status", "updated_at"])

        self.client.force_authenticate(self.leader)
        r = self.client.get(
            reverse("api_retreat_user_search"),
            {
                "event_id": self.event.id,
                "staff_pool": "1",
                "staff_pool_kind": "council",
                "q": "us_pastoral_multi",
            },
        )
        self.assertEqual(r.status_code, 200)
        rows = r.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["username"], pastoral_user.username)
        self.assertTrue(rows[0]["is_pastoral"])
        affiliation_division_ids = sorted(
            [row["division_id"] for row in rows[0]["affiliations"]]
        )
        self.assertEqual(affiliation_division_ids, sorted([self.div.id, div_univ.id]))
