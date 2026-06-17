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

    def test_pastor_onboarding_forbidden(self):
        self.client.force_login(self.pastor)
        r = self.client.get(reverse("user_onboarding_approvals"))
        self.assertEqual(r.status_code, 403)

    def test_staff_can_open_account_tab(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)

    def test_staff_can_open_onboarding_tab(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_onboarding_approvals"))
        self.assertEqual(r.status_code, 200)

    def test_manager_can_open_account_tab(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)

    def test_manager_can_open_onboarding_tab(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse("user_onboarding_approvals"))
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


class OnboardingApprovalAllDivisionsTests(AccountManageFixture):
    """가입 승인 '전체(담당 부서 전체)' 조회 동작."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.pending_a = User.objects.create_user(username="acct_pending_a", password="x")
        prof_a = ensure_user_profile(cls.pending_a)
        prof_a.real_name = "대기A"
        prof_a.onboarding_status = UserProfile.OnboardingStatus.PENDING
        prof_a.requested_division = cls.div_a
        prof_a.save()
        cls.prof_a = prof_a

        cls.pending_b = User.objects.create_user(username="acct_pending_b", password="x")
        prof_b = ensure_user_profile(cls.pending_b)
        prof_b.real_name = "대기B"
        prof_b.onboarding_status = UserProfile.OnboardingStatus.PENDING
        prof_b.requested_division = cls.div_b
        prof_b.save()
        cls.prof_b = prof_b

        cls.pending_c = User.objects.create_user(username="acct_pending_c", password="x")
        prof_c = ensure_user_profile(cls.pending_c)
        prof_c.real_name = "대기C"
        prof_c.onboarding_status = UserProfile.OnboardingStatus.PENDING
        prof_c.requested_division = cls.div_c
        prof_c.save()
        cls.prof_c = prof_c

    def test_superuser_all_shows_every_allowed_division(self):
        self.client.force_login(self.superuser)
        r = self.client.get(
            reverse("user_onboarding_approvals"),
            {"division_code": "__all__"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context["active_division"])
        pending_ids = {p.id for p in r.context["pending_profiles"]}
        self.assertIn(self.prof_a.id, pending_ids)
        self.assertIn(self.prof_b.id, pending_ids)

    def test_staff_all_shows_every_division(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_onboarding_approvals"),
            {"division_code": "__all__"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context["active_division"])
        pending_ids = {p.id for p in r.context["pending_profiles"]}
        self.assertIn(self.prof_a.id, pending_ids)
        self.assertIn(self.prof_b.id, pending_ids)
        self.assertIn(self.prof_c.id, pending_ids)

    def test_specific_division_filters_out_others(self):
        self.client.force_login(self.superuser)
        r = self.client.get(
            reverse("user_onboarding_approvals"),
            {"division_code": self.div_a.code},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["active_division"].id, self.div_a.id)
        pending_ids = {p.id for p in r.context["pending_profiles"]}
        self.assertIn(self.prof_a.id, pending_ids)
        self.assertNotIn(self.prof_b.id, pending_ids)

    def test_manager_all_limited_to_membership_divisions(self):
        # 계정관리권한자는 소속 부서(div_a, div_b)만 — div_c 신청은 보이지 않는다.
        self.client.force_login(self.manager)
        r = self.client.get(
            reverse("user_onboarding_approvals"),
            {"division_code": "__all__"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context["active_division"])
        pending_ids = {p.id for p in r.context["pending_profiles"]}
        self.assertIn(self.prof_a.id, pending_ids)
        self.assertIn(self.prof_b.id, pending_ids)
        self.assertNotIn(self.prof_c.id, pending_ids)
