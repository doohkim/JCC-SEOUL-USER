"""페이지별 권한 함수 단위 테스트."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from users.models import Division, Region, RoleLevel, UserDivisionTeam
from users.models.organization import Team
from users.permissions import (
    can_access_attendance_dashboard,
    can_access_attendance_roster_input,
    can_access_member_registry,
    can_access_team_roster_tab,
    is_attendance_manager,
)

User = get_user_model()


class PagePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="perm_youth", name="권한테스트청년부"
        )
        cls.team = Team.objects.create(
            division=cls.div, code="perm_t1", name="1팀", sort_order=1
        )
        cls.pastor_rl, _ = RoleLevel.objects.get_or_create(
            code="pastor", defaults={"name": "목사", "level": 90, "sort_order": 1}
        )
        cls.member_rl, _ = RoleLevel.objects.get_or_create(
            code="member_test", defaults={"name": "성도", "level": 10, "sort_order": 99}
        )

    def _user(self, username: str, **kwargs) -> User:
        u = User.objects.create_user(username=username, password="x")
        for k, v in kwargs.items():
            setattr(u, k, v)
        u.save()
        return u

    def test_attendance_manager_gets_team_roster_and_dashboard_not_registry(self):
        u = self._user("att_mgr", can_manage_attendance=True, role_level=self.member_rl)
        UserDivisionTeam.objects.create(
            user=u, division=self.div, team=self.team, is_primary=True
        )
        self.assertTrue(is_attendance_manager(u))
        self.assertTrue(can_access_team_roster_tab(u))
        self.assertTrue(can_access_attendance_dashboard(u))
        self.assertTrue(can_access_attendance_roster_input(u))
        self.assertFalse(can_access_member_registry(u))

    def test_pastor_gets_registry_and_attendance_pages(self):
        u = self._user("pastor_u", role_level=self.pastor_rl)
        self.assertTrue(can_access_member_registry(u))
        self.assertTrue(can_access_team_roster_tab(u))
        self.assertTrue(can_access_attendance_dashboard(u))

    def test_plain_member_with_division_gets_dashboard_only(self):
        u = self._user("plain", role_level=self.member_rl)
        UserDivisionTeam.objects.create(
            user=u, division=self.div, team=self.team, is_primary=True
        )
        self.assertTrue(can_access_attendance_dashboard(u))
        self.assertFalse(can_access_team_roster_tab(u))
        self.assertFalse(can_access_attendance_roster_input(u))
        self.assertFalse(can_access_member_registry(u))

    def test_member_without_division_denied_attendance_pages(self):
        u = self._user("nodiv", role_level=self.member_rl)
        self.assertFalse(can_access_attendance_dashboard(u))
        self.assertFalse(can_access_team_roster_tab(u))
