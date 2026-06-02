"""`permission_tags` 템플릿 태그/필터 단위 회귀 테스트."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from users.models import Division, Region, RoleLevel, UserDivisionTeam
from users.models.organization import Team
from users.templatetags.permission_tags import user_org_summary

User = get_user_model()


class UserOrgSummaryFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="org_youth", name="청년부"
        )
        cls.team = Team.objects.create(
            division=cls.div, code="team1", name="1팀", sort_order=1
        )
        cls.role, _ = RoleLevel.objects.get_or_create(
            code="staff_test", defaults={"name": "간사", "level": 30, "sort_order": 10}
        )

    def test_anonymous_returns_empty(self):
        self.assertEqual(user_org_summary(AnonymousUser()), "")

    def test_user_with_no_division_returns_only_role(self):
        u = User.objects.create_user(username="org_norel", password="x")
        u.role_level = self.role
        u.save()
        self.assertEqual(user_org_summary(u), "간사")

    def test_user_with_no_division_no_role_returns_empty(self):
        u = User.objects.create_user(username="org_empty", password="x")
        self.assertEqual(user_org_summary(u), "")

    def test_full_summary_includes_region_division_team_role(self):
        u = User.objects.create_user(username="org_full", password="x")
        u.role_level = self.role
        u.save()
        UserDivisionTeam.objects.create(
            user=u, division=self.div, team=self.team, is_primary=True
        )
        self.assertEqual(user_org_summary(u), "서울 · 청년부 · 1팀 · 간사")

    def test_summary_without_team(self):
        u = User.objects.create_user(username="org_no_team", password="x")
        UserDivisionTeam.objects.create(
            user=u, division=self.div, team=None, is_primary=True
        )
        self.assertEqual(user_org_summary(u), "서울 · 청년부")

    def test_primary_division_is_preferred(self):
        u = User.objects.create_user(username="org_primary", password="x")
        other_div = Division.objects.create(
            region=self.seoul, code="org_kids", name="유년부"
        )
        UserDivisionTeam.objects.create(
            user=u, division=other_div, is_primary=False, sort_order=1
        )
        UserDivisionTeam.objects.create(
            user=u, division=self.div, is_primary=True, sort_order=2
        )
        self.assertEqual(user_org_summary(u), "서울 · 청년부")
