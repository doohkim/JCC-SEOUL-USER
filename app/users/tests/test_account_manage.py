"""계정 탭 통합 편집기·기본 부서·권한 테스트."""

from __future__ import annotations

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

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

    def _post_memberships(self, user, memberships, removed_actions=None):
        payload = {
            "user_id": str(self.member.id),
            "real_name": "멤버",
            "phone": "",
            "division_id": str(self.div_a.id),
            "team_id": str(self.team_a.id),
            "memberships_payload": json.dumps(memberships, ensure_ascii=False),
            "removed_membership_actions": json.dumps(
                removed_actions or [], ensure_ascii=False
            ),
        }
        self.client.force_login(user)
        return self.client.post(reverse("user_division_account_roles"), payload)

    def test_manager_can_change_team_only(self):
        self.client.force_login(self.manager)
        r = self._post_row(self.manager, {"team_id": str(self.team_a2.id)})
        self.assertEqual(r.status_code, 302)
        membership = UserDivisionTeam.objects.get(user=self.member, division=self.div_a)
        self.assertEqual(membership.team_id, self.team_a2.id)

    def test_manager_phone_digits_normalized_on_save(self):
        self.client.force_login(self.manager)
        r = self._post_row(self.manager, {"phone": "01044442222"})
        self.assertEqual(r.status_code, 302)
        profile = ensure_user_profile(self.member)
        profile.refresh_from_db()
        self.assertEqual(profile.phone, "010-4444-2222")

    def test_manager_can_update_gender(self):
        self.client.force_login(self.staff)
        r = self._post_row(self.staff, {"gender": UserProfile.Gender.FEMALE})
        self.assertEqual(r.status_code, 302)
        profile = ensure_user_profile(self.member)
        profile.refresh_from_db()
        self.assertEqual(profile.gender, UserProfile.Gender.FEMALE)

    def test_manager_rejects_invalid_gender(self):
        self.client.force_login(self.staff)
        profile = ensure_user_profile(self.member)
        profile.gender = UserProfile.Gender.MALE
        profile.save(update_fields=["gender"])
        r = self._post_row(self.staff, {"gender": "other"})
        self.assertEqual(r.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.gender, UserProfile.Gender.MALE)

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
        membership = UserDivisionTeam.objects.get(user=self.member, division=self.div_b)
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
        membership = UserDivisionTeam.objects.get(user=self.member, division=self.div_b)
        self.assertEqual(membership.team_id, self.team_b.id)

    def test_staff_can_save_multi_memberships_payload(self):
        r = self._post_memberships(
            self.staff,
            [
                {
                    "division_id": self.div_b.id,
                    "team_id": self.team_b.id,
                    "is_primary": True,
                    "sort_order": 0,
                },
                {
                    "division_id": self.div_a.id,
                    "team_id": self.team_a2.id,
                    "is_primary": True,
                    "sort_order": 1,
                },
            ],
        )
        self.assertEqual(r.status_code, 302)
        rows = list(
            UserDivisionTeam.objects.filter(
                user=self.member, division_id__in=[self.div_a.id, self.div_b.id]
            ).order_by("sort_order", "division__sort_order")
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].division_id, self.div_b.id)
        self.assertEqual(rows[0].team_id, self.team_b.id)
        self.assertTrue(rows[0].is_primary)
        self.assertEqual(rows[1].division_id, self.div_a.id)
        self.assertEqual(rows[1].team_id, self.team_a2.id)
        self.assertTrue(rows[1].is_primary)

        profile = ensure_user_profile(self.member)
        profile.refresh_from_db()
        self.assertEqual(profile.requested_division_id, self.div_b.id)
        self.assertEqual(profile.requested_team_id, self.team_b.id)

    def test_memberships_payload_rejects_duplicate_division(self):
        before_count = UserDivisionTeam.objects.filter(user=self.member).count()
        r = self._post_memberships(
            self.staff,
            [
                {
                    "division_id": self.div_a.id,
                    "team_id": self.team_a.id,
                    "is_primary": True,
                    "sort_order": 0,
                },
                {
                    "division_id": self.div_a.id,
                    "team_id": self.team_a2.id,
                    "is_primary": False,
                    "sort_order": 1,
                },
            ],
        )
        self.assertEqual(r.status_code, 302)
        after_count = UserDivisionTeam.objects.filter(user=self.member).count()
        self.assertEqual(before_count, after_count)
        self.assertTrue(
            UserDivisionTeam.objects.filter(
                user=self.member, division=self.div_a, team=self.team_a
            ).exists()
        )

    def test_memberships_payload_rejects_team_division_mismatch(self):
        r = self._post_memberships(
            self.staff,
            [
                {
                    "division_id": self.div_a.id,
                    "team_id": self.team_b.id,
                    "is_primary": True,
                    "sort_order": 0,
                }
            ],
        )
        self.assertEqual(r.status_code, 302)
        membership = UserDivisionTeam.objects.get(user=self.member, division=self.div_a)
        self.assertEqual(membership.team_id, self.team_a.id)

    def test_remove_mode_deletes_only_active_retreat_assignments(self):
        active_event = RetreatEvent.objects.create(
            name="활성 집회",
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 12),
            is_active=True,
        )
        inactive_event = RetreatEvent.objects.create(
            name="비활성 집회",
            start_date=date(2026, 8, 13),
            end_date=date(2026, 8, 15),
            is_active=False,
        )
        active_group = RetreatGroup.objects.create(
            event=active_event,
            region=self.seoul,
            division=self.div_a,
            name="1조",
        )
        inactive_group = RetreatGroup.objects.create(
            event=inactive_event,
            region=self.seoul,
            division=self.div_a,
            name="2조",
        )
        RetreatCouncilMembership.objects.create(
            event=active_event,
            user=self.member,
            role=RetreatCouncilMembership.Role.DIVISION_ADMIN,
            division=self.div_a,
        )
        RetreatCouncilMembership.objects.create(
            event=inactive_event,
            user=self.member,
            role=RetreatCouncilMembership.Role.DIVISION_ADMIN,
            division=self.div_a,
        )
        RetreatGroupMembership.objects.create(
            user=self.member,
            group=active_group,
            role=RetreatGroupMembership.Role.LEADER,
        )
        RetreatGroupMembership.objects.create(
            user=self.member,
            group=inactive_group,
            role=RetreatGroupMembership.Role.VICE_LEADER,
        )

        r = self._post_memberships(
            self.staff,
            [
                {
                    "division_id": self.div_b.id,
                    "team_id": self.team_b.id,
                    "is_primary": True,
                    "sort_order": 0,
                }
            ],
            removed_actions=[
                {
                    "division_id": self.div_a.id,
                    "remove_mode": "membership_and_retreat_assignments",
                    "expected_active_event_count": 1,
                    "expected_council_count": 1,
                    "expected_group_count": 1,
                }
            ],
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            RetreatCouncilMembership.objects.filter(
                event=active_event, user=self.member
            ).exists()
        )
        self.assertTrue(
            RetreatCouncilMembership.objects.filter(
                event=inactive_event, user=self.member
            ).exists()
        )
        self.assertFalse(
            RetreatGroupMembership.objects.filter(
                group=active_group, user=self.member
            ).exists()
        )
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=inactive_group, user=self.member
            ).exists()
        )

    def test_hybrid_blocks_when_unassign_mode_preview_mismatch(self):
        active_event = RetreatEvent.objects.create(
            name="활성 집회 mismatch",
            start_date=date(2026, 8, 20),
            end_date=date(2026, 8, 22),
            is_active=True,
        )
        active_group = RetreatGroup.objects.create(
            event=active_event,
            region=self.seoul,
            division=self.div_a,
            name="3조",
        )
        RetreatCouncilMembership.objects.create(
            event=active_event,
            user=self.member,
            role=RetreatCouncilMembership.Role.DIVISION_ADMIN,
            division=self.div_a,
        )
        RetreatGroupMembership.objects.create(
            user=self.member,
            group=active_group,
            role=RetreatGroupMembership.Role.LEADER,
        )

        r = self._post_memberships(
            self.staff,
            [
                {
                    "division_id": self.div_b.id,
                    "team_id": self.team_b.id,
                    "is_primary": True,
                    "sort_order": 0,
                }
            ],
            removed_actions=[
                {
                    "division_id": self.div_a.id,
                    "remove_mode": "membership_and_retreat_assignments",
                    "expected_active_event_count": 0,
                    "expected_council_count": 0,
                    "expected_group_count": 0,
                }
            ],
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
        self.assertTrue(
            RetreatCouncilMembership.objects.filter(
                event=active_event, user=self.member
            ).exists()
        )
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=active_group, user=self.member
            ).exists()
        )

    def test_hybrid_allows_membership_only_when_preview_mismatch(self):
        active_event = RetreatEvent.objects.create(
            name="활성 집회 soft",
            start_date=date(2026, 8, 23),
            end_date=date(2026, 8, 25),
            is_active=True,
        )
        active_group = RetreatGroup.objects.create(
            event=active_event,
            region=self.seoul,
            division=self.div_a,
            name="4조",
        )
        RetreatCouncilMembership.objects.create(
            event=active_event,
            user=self.member,
            role=RetreatCouncilMembership.Role.DIVISION_ADMIN,
            division=self.div_a,
        )
        RetreatGroupMembership.objects.create(
            user=self.member,
            group=active_group,
            role=RetreatGroupMembership.Role.LEADER,
        )

        r = self._post_memberships(
            self.staff,
            [
                {
                    "division_id": self.div_b.id,
                    "team_id": self.team_b.id,
                    "is_primary": True,
                    "sort_order": 0,
                }
            ],
            removed_actions=[
                {
                    "division_id": self.div_a.id,
                    "remove_mode": "membership_only",
                    "expected_active_event_count": 0,
                    "expected_council_count": 0,
                    "expected_group_count": 0,
                }
            ],
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            UserDivisionTeam.objects.filter(
                user=self.member, division=self.div_a
            ).exists()
        )
        self.assertTrue(
            UserDivisionTeam.objects.filter(
                user=self.member, division=self.div_b
            ).exists()
        )
        self.assertTrue(
            RetreatCouncilMembership.objects.filter(
                event=active_event, user=self.member
            ).exists()
        )
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=active_group, user=self.member
            ).exists()
        )

    def test_reject_removed_actions_for_non_removed_division(self):
        r = self._post_memberships(
            self.staff,
            [
                {
                    "division_id": self.div_a.id,
                    "team_id": self.team_a.id,
                    "is_primary": True,
                    "sort_order": 0,
                },
                {
                    "division_id": self.div_b.id,
                    "team_id": self.team_b.id,
                    "is_primary": False,
                    "sort_order": 1,
                },
            ],
            removed_actions=[
                {
                    "division_id": self.div_b.id,
                    "remove_mode": "membership_and_retreat_assignments",
                    "expected_active_event_count": 0,
                    "expected_council_count": 0,
                    "expected_group_count": 0,
                }
            ],
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
