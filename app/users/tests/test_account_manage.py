"""계정 탭 통합 편집기·기본 부서·권한 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from retreat.models import RetreatEvent, RetreatGroup, RetreatGroupMembership
from users.mixins import ensure_user_profile
from users.models import (
    Division,
    PastoralDivisionAssignment,
    Region,
    RoleLevel,
    Team,
    UserDivisionTeam,
    UserProfile,
)

User = get_user_model()


class AccountManageFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div_a = Division.objects.create(
            region=cls.seoul, code="acct_div_a", name="청년부", sort_order=1
        )
        cls.div_b = Division.objects.create(
            region=cls.seoul, code="acct_div_b", name="대학부", sort_order=2
        )
        cls.team_a = Team.objects.create(
            division=cls.div_a, code="acct_t1", name="1팀", sort_order=1
        )
        cls.team_a2 = Team.objects.create(
            division=cls.div_a, code="acct_t1b", name="2팀", sort_order=2
        )
        cls.team_b = Team.objects.create(
            division=cls.div_b, code="acct_t2", name="대학1팀", sort_order=1
        )

        cls.rl_pastor, _ = RoleLevel.objects.get_or_create(
            code="pastor",
            defaults={"name": "목사", "level": 90, "sort_order": 5},
        )

        cls.pastor = User.objects.create_user(username="acct_pastor", password="x")
        cls.pastor.role_level = cls.rl_pastor
        cls.pastor.save()
        PastoralDivisionAssignment.objects.create(user=cls.pastor, division=cls.div_a)

        cls.manager = User.objects.create_user(username="acct_manager", password="x")
        cls.manager.can_manage_accounts = True
        cls.manager.save()
        UserDivisionTeam.objects.create(
            user=cls.manager, division=cls.div_a, team=cls.team_a, is_primary=True
        )
        UserDivisionTeam.objects.create(
            user=cls.manager, division=cls.div_b, is_primary=False, sort_order=1
        )

        cls.superuser = User.objects.create_superuser(
            username="acct_super", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.superuser, division=cls.div_a, is_primary=True
        )

        cls.member = User.objects.create_user(username="acct_member", password="x")
        UserDivisionTeam.objects.create(
            user=cls.member, division=cls.div_a, team=cls.team_a, is_primary=True
        )
        profile = ensure_user_profile(cls.member)
        profile.real_name = "멤버"
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.requested_division = cls.div_a
        profile.requested_team = cls.team_a
        profile.save()

        cls.event = RetreatEvent.objects.create(
            name="계정관리 테스트 수련회",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
            is_active=True,
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_a,
            name="1조",
        )

    def setUp(self):
        self.client = Client()


class AccountManageAccessTests(AccountManageFixture):
    def test_pastor_without_manage_flag_forbidden(self):
        self.client.force_login(self.pastor)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 403)

    def test_manager_can_open_account_tab(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)


class AccountManageDefaultDivisionTests(AccountManageFixture):
    def test_manager_defaults_to_own_primary_division(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["active_division"].id, self.div_a.id)

    def test_manager_can_filter_other_manageable_division(self):
        self.client.force_login(self.manager)
        r = self.client.get(
            reverse("user_division_account_roles"),
            {"division_code": self.div_b.code},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["active_division"].id, self.div_b.id)


class AccountManagePostTests(AccountManageFixture):
    def _post_row(self, user, data):
        payload = {
            "user_id": str(self.member.id),
            "real_name": "멤버",
            "phone": "",
            "division_id": str(self.div_a.id),
            "team_id": str(self.team_a.id),
        }
        payload.update(data)
        return self.client.post(reverse("user_division_account_roles"), payload)

    def test_manager_can_change_team_only(self):
        self.client.force_login(self.manager)
        r = self._post_row(self.manager, {"team_id": str(self.team_a2.id)})
        self.assertEqual(r.status_code, 302)
        membership = UserDivisionTeam.objects.get(
            user=self.member, division=self.div_a
        )
        self.assertEqual(membership.team_id, self.team_a2.id)

    def test_manager_cannot_move_division(self):
        self.client.force_login(self.manager)
        r = self._post_row(
            self.manager,
            {"division_id": str(self.div_b.id), "team_id": str(self.team_b.id)},
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            UserDivisionTeam.objects.filter(
                user=self.member, division=self.div_a
            ).exists()
        )
        self.assertFalse(
            UserDivisionTeam.objects.filter(
                user=self.member, division=self.div_b
            ).exists()
        )

    def test_superuser_can_move_division(self):
        self.client.force_login(self.superuser)
        r = self._post_row(
            self.superuser,
            {
                "division_id": str(self.div_b.id),
                "team_id": str(self.team_b.id),
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            UserDivisionTeam.objects.filter(
                user=self.member, division=self.div_a
            ).exists()
        )
        membership = UserDivisionTeam.objects.get(
            user=self.member, division=self.div_b
        )
        self.assertEqual(membership.team_id, self.team_b.id)

    def test_superuser_can_assign_retreat_group(self):
        self.client.force_login(self.superuser)
        # member back in div_a for retreat group scope
        UserDivisionTeam.objects.filter(user=self.member).delete()
        UserDivisionTeam.objects.create(
            user=self.member, division=self.div_a, team=self.team_a, is_primary=True
        )
        r = self._post_row(
            self.superuser,
            {
                "retreat_group_id": str(self.group.id),
                "retreat_role": "participant",
            },
        )
        self.assertEqual(r.status_code, 302)
        profile = UserProfile.objects.get(user=self.member)
        self.assertEqual(profile.requested_retreat_group_id, self.group.id)
        self.assertTrue(profile.requested_retreat_participation)
