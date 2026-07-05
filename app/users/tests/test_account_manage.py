"""계정 탭 통합 편집기·기본 부서·권한 테스트."""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

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
        cls.div_c = Division.objects.create(
            region=cls.seoul, code="acct_div_c", name="유년부", sort_order=3
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
        cls.team_c = Team.objects.create(
            division=cls.div_c, code="acct_t3", name="유년1팀", sort_order=1
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

        cls.staff = User.objects.create_user(
            username="acct_staff", password="x", is_staff=True
        )
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.div_a, team=cls.team_a, is_primary=True
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

        cls.member_c = User.objects.create_user(username="acct_member_c", password="x")
        UserDivisionTeam.objects.create(
            user=cls.member_c, division=cls.div_c, team=cls.team_c, is_primary=True
        )
        profile_c = ensure_user_profile(cls.member_c)
        profile_c.real_name = "유년멤버"
        profile_c.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile_c.requested_division = cls.div_c
        profile_c.requested_team = cls.team_c
        profile_c.save()

    def setUp(self):
        self.client = Client()


class AccountManageAccessTests(AccountManageFixture):
    def test_pastor_without_manage_flag_forbidden(self):
        self.client.force_login(self.pastor)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 403)

    def test_onboarding_applications_url_redirects_to_roles(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_onboarding_applications"))
        self.assertRedirects(r, reverse("user_division_account_roles"))

    def test_legacy_onboarding_approvals_url_redirects_to_roles(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_onboarding_approvals"))
        self.assertRedirects(r, reverse("user_division_account_roles"))

    def test_onboarding_activity_log_url_redirects_to_roles(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_onboarding_application_activity_log"))
        self.assertRedirects(r, reverse("user_division_account_roles"))

    def test_staff_can_open_account_tab(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)

    def test_manager_can_open_account_tab(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)


class AccountManageScopeTests(AccountManageFixture):
    def test_staff_sees_all_divisions_in_choices(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)
        choice_ids = {d.id for d in r.context["allowed_divisions"]}
        self.assertIn(self.div_a.id, choice_ids)
        self.assertIn(self.div_b.id, choice_ids)
        self.assertIn(self.div_c.id, choice_ids)

    def test_manager_sees_only_membership_divisions(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)
        choice_ids = {d.id for d in r.context["allowed_divisions"]}
        self.assertIn(self.div_a.id, choice_ids)
        self.assertIn(self.div_b.id, choice_ids)
        self.assertNotIn(self.div_c.id, choice_ids)


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

    def test_manager_phone_digits_normalized_on_save(self):
        self.client.force_login(self.manager)
        r = self._post_row(self.manager, {"phone": "01044442222"})
        self.assertEqual(r.status_code, 302)
        profile = ensure_user_profile(self.member)
        profile.refresh_from_db()
        self.assertEqual(profile.phone, "010-4444-2222")

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

    def test_staff_can_move_division(self):
        self.client.force_login(self.staff)
        r = self._post_row(
            self.staff,
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


class DivisionAccountActivityLogTests(AccountManageFixture):
    def test_roles_page_excludes_retreat_section_in_account_modal(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_division_account_roles"),
            {"division_code": self.div_a.code},
        )
        self.assertEqual(r.status_code, 200)
        details = json.loads(r.context["account_details_json"])
        member_detail = details[str(self.member.id)]
        self.assertNotIn("retreat_by_event", member_detail)
        self.assertNotContains(r, "accountRetreatSection")
        self.assertNotContains(r, "jccAccountRetreatGroupsByEventJson")
        self.assertNotContains(r, "가입 신청 정보")

    def test_roles_page_includes_activity_log_ui(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("activity_log_url", r.context)
        self.assertContains(r, "accountActivityBtn")
        self.assertContains(r, "활동 로그")

    def test_activity_log_html_redirects_to_roles_modal(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_division_account_activity_log"),
            {"user_id": str(self.member.id), "division_code": self.div_a.code},
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("open_user=", r.url)
        self.assertIn("view=activity", r.url)

    def test_roles_page_includes_in_modal_activity_view(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "accountEditActivityView")
        self.assertContains(r, "accountActivityBack")
        self.assertContains(r, "accountActivityPagination")
        self.assertContains(r, "accountActivityScroll")
        self.assertContains(r, "jcc-actLogUser__nameLink")

    def test_activity_log_ok_for_allowed_user(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_division_account_activity_log"),
            {"user_id": str(self.member.id), "format": "json"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("items", data)
        self.assertTrue(len(data["items"]) >= 1)
        self.assertIn("category", data["items"][0])
        self.assertIn("tone", data["items"][0])

    def test_activity_log_forbidden_for_out_of_scope_user(self):
        self.client.force_login(self.manager)
        r = self.client.get(
            reverse("user_division_account_activity_log"),
            {"user_id": str(self.member_c.id), "format": "json"},
        )
        self.assertEqual(r.status_code, 403)
