"""계정 탭 통합 편집기·기본 부서·권한 테스트."""

from __future__ import annotations

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from retreat.models import RetreatAttendee, RetreatEvent, RetreatGroup, RetreatGroupMembership
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
from users.permissions import can_access_retreat_tab, visible_retreat_groups_for

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
        r = self.client.get(reverse("user_onboarding_applications"))
        self.assertEqual(r.status_code, 403)

    def test_staff_can_open_account_tab(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)

    def test_staff_can_open_onboarding_tab(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_onboarding_applications"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["account_tab"], "applications")

    def test_legacy_onboarding_approvals_url_redirects(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_onboarding_approvals"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("user_onboarding_applications"))

    def test_manager_can_open_account_tab(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse("user_division_account_roles"))
        self.assertEqual(r.status_code, 200)

    def test_manager_can_open_onboarding_tab(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse("user_onboarding_applications"))
        self.assertEqual(r.status_code, 200)


class OnboardingApplicationsDefaultFilterTests(AccountManageFixture):
    def test_staff_defaults_to_primary_division_region_and_all_status(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("user_onboarding_applications"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["active_division"].id, self.div_a.id)
        self.assertEqual(r.context["active_region_id"], str(self.seoul.id))
        self.assertEqual(r.context["status_filter"], "")

    def test_superuser_defaults_to_primary_division_when_member(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("user_onboarding_applications"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["active_division"].id, self.div_a.id)
        self.assertEqual(r.context["active_region_id"], str(self.seoul.id))

    def test_manager_defaults_to_primary_division(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse("user_onboarding_applications"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["active_division"].id, self.div_a.id)
        self.assertEqual(r.context["active_region_id"], str(self.seoul.id))

    def test_explicit_all_divisions_overrides_default(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_onboarding_applications"),
            {"division_code": "__all__"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context["active_division"])


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


class OnboardingApprovalMemberOnlyTests(AccountManageFixture):
    def test_list_shows_retreat_group_column(self):
        applicant = User.objects.create_user(username="acct_retreat_list", password="x")
        profile = ensure_user_profile(applicant)
        profile.real_name = "수련회신청"
        profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        profile.requested_division = self.div_a
        profile.requested_retreat_participation = True
        profile.requested_retreat_event = self.event
        profile.requested_retreat_group = self.group
        profile.save()

        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_onboarding_applications"),
            {"status": UserProfile.OnboardingStatus.PENDING},
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "수련회 신청 조")
        self.assertContains(r, self.group.name)

    def test_approve_via_action_without_onboarding_status_field(self):
        applicant = User.objects.create_user(username="acct_approve_action", password="x")
        profile = ensure_user_profile(applicant)
        profile.real_name = "액션승인"
        profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        profile.requested_division = self.div_a
        profile.requested_team = self.team_a
        profile.save()

        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            {
                "profile_id": str(profile.id),
                "action": "approve",
                "requested_division_id": str(self.div_a.id),
                "requested_team_id": str(self.team_a.id),
                "list_status": UserProfile.OnboardingStatus.PENDING,
            },
        )
        self.assertEqual(r.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.onboarding_status, UserProfile.OnboardingStatus.APPROVED)

    def test_approve_assigns_retreat_member_not_leader(self):
        applicant = User.objects.create_user(username="acct_retreat_app", password="x")
        profile = ensure_user_profile(applicant)
        profile.real_name = "수련회신청"
        profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        profile.requested_division = self.div_a
        profile.requested_retreat_participation = True
        profile.requested_retreat_event = self.event
        profile.requested_retreat_group = self.group
        profile.requested_retreat_role = "leader"
        profile.save()

        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            {
                "profile_id": str(profile.id),
                "action": "save",
                "onboarding_status": UserProfile.OnboardingStatus.APPROVED,
                "requested_division_id": str(self.div_a.id),
                "requested_team_id": str(self.team_a.id),
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            RetreatGroupMembership.objects.filter(user=applicant, group=self.group).exists()
        )
        attendee = RetreatAttendee.objects.get(group=self.group, user=applicant)
        self.assertEqual(attendee.member_role, RetreatAttendee.MemberRole.MEMBER)
        self.assertEqual(attendee.user_id, applicant.id)
        self.assertEqual(attendee.name, "수련회신청")

    def test_approve_with_retreat_group_in_post_creates_linked_attendee(self):
        """승인 요청 POST에 조가 포함되면 즉시 조원·계정 연동한다."""
        applicant = User.objects.create_user(username="acct_retreat_post", password="x")
        profile = ensure_user_profile(applicant)
        profile.real_name = "승인조배정"
        profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        profile.requested_division = self.div_a
        profile.requested_team = self.team_a
        profile.save()

        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            {
                "profile_id": str(profile.id),
                "action": "save",
                "onboarding_status": UserProfile.OnboardingStatus.APPROVED,
                "requested_division_id": str(self.div_a.id),
                "requested_team_id": str(self.team_a.id),
                "requested_retreat_event_id": str(self.event.id),
                "requested_retreat_group_id": str(self.group.id),
            },
        )
        self.assertEqual(r.status_code, 302)
        attendee = RetreatAttendee.objects.get(group=self.group, user=applicant)
        self.assertEqual(attendee.member_role, RetreatAttendee.MemberRole.MEMBER)
        self.assertEqual(attendee.name, "승인조배정")

    def test_approve_pastoral_applicant_skips_retreat_attendee_even_with_group(self):
        applicant = User.objects.create_user(username="acct_pastor_app", password="x")
        profile = ensure_user_profile(applicant)
        profile.real_name = "목사신청"
        profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        profile.requested_division = self.div_a
        profile.requested_team = self.team_a
        profile.requested_applicant_role = UserProfile.ApplicantRole.PASTOR
        profile.requested_retreat_participation = True
        profile.requested_retreat_event = self.event
        profile.requested_retreat_group = self.group
        profile.save()

        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            {
                "profile_id": str(profile.id),
                "action": "save",
                "onboarding_status": UserProfile.OnboardingStatus.APPROVED,
                "requested_division_id": str(self.div_a.id),
                "requested_team_id": str(self.team_a.id),
                "requested_retreat_event_id": str(self.event.id),
                "requested_retreat_group_id": str(self.group.id),
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            RetreatAttendee.objects.filter(group=self.group, user=applicant).exists()
        )
        applicant.refresh_from_db()
        self.assertEqual(applicant.role_level_id, self.rl_pastor.id)
        self.assertTrue(
            PastoralDivisionAssignment.objects.filter(
                user=applicant, division=self.div_a
            ).exists()
        )
        self.assertTrue(can_access_retreat_tab(applicant))
        self.assertTrue(
            visible_retreat_groups_for(applicant, self.event).filter(pk=self.group.pk).exists()
        )

    def test_approve_with_group_only_when_participation_flag_false(self):
        """참여 플래그가 꺼져 있어도 조가 지정돼 있으면 조원으로 등록한다."""
        applicant = User.objects.create_user(username="acct_retreat_flag", password="x")
        profile = ensure_user_profile(applicant)
        profile.real_name = "플래그불일치"
        profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        profile.requested_division = self.div_a
        profile.requested_retreat_participation = False
        profile.requested_retreat_event = self.event
        profile.requested_retreat_group = self.group
        profile.save()

        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            {
                "profile_id": str(profile.id),
                "action": "approve",
                "requested_division_id": str(self.div_a.id),
                "requested_team_id": str(self.team_a.id),
            },
        )
        self.assertEqual(r.status_code, 302)
        attendee = RetreatAttendee.objects.get(group=self.group, user=applicant)
        self.assertEqual(attendee.name, "플래그불일치")


class OnboardingApplicationStatusSaveTests(AccountManageFixture):
    """목록 행 저장 폼(action=save + onboarding_status) 승인·반려 동작."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.applicant = User.objects.create_user(username="acct_status_save", password="x")
        cls.profile = ensure_user_profile(cls.applicant)
        cls.profile.real_name = "승인저장테스트"
        cls.profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        cls.profile.requested_division = cls.div_a
        cls.profile.requested_team = cls.team_a
        cls.profile.save()

    def _row_save_payload(self, **overrides):
        payload = {
            "profile_id": str(self.profile.id),
            "action": "save",
            "onboarding_status": UserProfile.OnboardingStatus.APPROVED,
            "requested_division_id": str(self.div_a.id),
            "requested_team_id": str(self.team_a.id),
            "date_from": "2026-03-24",
            "date_to": "2026-06-22",
            "region_id": str(self.seoul.id),
            "division_code": self.div_a.code,
            "list_status": UserProfile.OnboardingStatus.PENDING,
            "page": "1",
        }
        payload.update(overrides)
        return payload

    def test_list_pending_row_exposes_named_status_select(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_onboarding_applications"),
            {
                "status": UserProfile.OnboardingStatus.PENDING,
                "division_code": self.div_a.code,
            },
        )
        self.assertEqual(r.status_code, 200)
        form_id = f"save-{self.profile.id}"
        self.assertContains(r, 'name="onboarding_status"')
        self.assertContains(r, f'form="{form_id}"')
        self.assertContains(r, f'id="{form_id}"')
        self.assertNotContains(r, 'class="js-apps-status-value"', html=False)

    def test_approve_via_save_action_and_onboarding_status(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            self._row_save_payload(),
        )
        self.assertEqual(r.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.OnboardingStatus.APPROVED)

    def test_approve_via_save_creates_primary_membership(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            self._row_save_payload(),
        )
        self.assertEqual(r.status_code, 302)
        membership = UserDivisionTeam.objects.get(
            user=self.applicant,
            division=self.div_a,
        )
        self.assertTrue(membership.is_primary)
        self.assertEqual(membership.team_id, self.team_a.id)

    def test_reject_via_save_action_and_onboarding_status(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            self._row_save_payload(
                onboarding_status=UserProfile.OnboardingStatus.REJECTED,
            ),
        )
        self.assertEqual(r.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.OnboardingStatus.REJECTED)

    def test_save_with_pending_status_does_not_approve(self):
        """드롭다운 값이 pending 으로 전송되면 승인되지 않아야 한다 (회귀 방지)."""
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            self._row_save_payload(
                onboarding_status=UserProfile.OnboardingStatus.PENDING,
            ),
        )
        self.assertEqual(r.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.OnboardingStatus.PENDING)
        self.assertFalse(
            UserDivisionTeam.objects.filter(user=self.applicant).exists()
        )

    def test_save_without_onboarding_status_field_rejects_request(self):
        """onboarding_status 가 POST 에 없으면 승인 처리되지 않는다."""
        self.client.force_login(self.staff)
        payload = self._row_save_payload()
        del payload["onboarding_status"]
        r = self.client.post(reverse("user_onboarding_applications"), payload)
        self.assertEqual(r.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.OnboardingStatus.PENDING)


class OnboardingRetreatSyncTests(AccountManageFixture):
    """승인·신청서 수정 시 수련회 조원(RetreatAttendee) 동기화."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.applicant = User.objects.create_user(username="acct_retreat_sync", password="x")
        cls.profile = ensure_user_profile(cls.applicant)
        cls.profile.real_name = "수련회동기화"
        cls.profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        cls.profile.requested_division = cls.div_a
        cls.profile.requested_team = cls.team_a
        cls.profile.requested_retreat_participation = True
        cls.profile.requested_retreat_event = cls.event
        cls.profile.requested_retreat_group = cls.group
        cls.profile.save()

    def test_resave_approved_application_creates_missing_attendee(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            {
                "profile_id": str(self.profile.id),
                "action": "save",
                "onboarding_status": UserProfile.OnboardingStatus.APPROVED,
                "requested_division_id": str(self.div_a.id),
                "requested_team_id": str(self.team_a.id),
            },
        )
        self.assertEqual(r.status_code, 302)
        attendee = RetreatAttendee.objects.filter(
            group=self.group, user=self.applicant
        ).first()
        self.assertIsNotNone(attendee)
        self.assertEqual(attendee.member_role, RetreatAttendee.MemberRole.MEMBER)

    def test_update_profile_on_approved_user_creates_missing_attendee(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            {
                "profile_id": str(self.profile.id),
                "action": "update_profile",
                "real_name": "수련회동기화",
                "phone": "",
                "requested_division_id": str(self.div_a.id),
                "requested_team_id": str(self.team_a.id),
                "requested_retreat_event_id": str(self.event.id),
                "requested_retreat_group_id": str(self.group.id),
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            RetreatAttendee.objects.filter(group=self.group, user=self.applicant).exists()
        )


class OnboardingApplicationsPaginationTests(AccountManageFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for i in range(21):
            user = User.objects.create_user(username=f"acct_page_{i:02d}", password="x")
            profile = ensure_user_profile(user)
            profile.real_name = f"페이지{i:02d}"
            profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
            profile.requested_division = cls.div_a
            profile.save()

    def test_first_page_lists_twenty_items(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_onboarding_applications"),
            {
                "status": UserProfile.OnboardingStatus.PENDING,
                "division_code": self.div_a.code,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["application_profiles"]), 20)
        self.assertEqual(r.context["page_size"], 20)
        self.assertTrue(r.context["is_paginated"])
        self.assertContains(r, "1 / 2페이지")

    def test_second_page_lists_remainder(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_onboarding_applications"),
            {
                "status": UserProfile.OnboardingStatus.PENDING,
                "division_code": self.div_a.code,
                "page": "2",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["application_profiles"]), 1)
        self.assertEqual(r.context["page_obj"].number, 2)


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
            reverse("user_onboarding_applications"),
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
            reverse("user_onboarding_applications"),
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
            reverse("user_onboarding_applications"),
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
            reverse("user_onboarding_applications"),
            {"division_code": "__all__"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context["active_division"])
        pending_ids = {p.id for p in r.context["pending_profiles"]}
        self.assertIn(self.prof_a.id, pending_ids)
        self.assertIn(self.prof_b.id, pending_ids)
        self.assertNotIn(self.prof_c.id, pending_ids)


class OnboardingApplicationEditTests(AccountManageFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.applicant = User.objects.create_user(username="kakao_edit01", password="x")
        cls.profile = ensure_user_profile(cls.applicant)
        cls.profile.real_name = "편집대상"
        cls.profile.display_name = "표시명"
        cls.profile.phone = "010-1111-2222"
        cls.profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        cls.profile.requested_division = cls.div_a
        cls.profile.requested_team = cls.team_a
        cls.profile.requested_retreat_participation = True
        cls.profile.requested_retreat_event = cls.event
        cls.profile.requested_retreat_group = cls.group
        cls.profile.save()

        cls.other_applicant = User.objects.create_user(username="kakao_other", password="x")
        cls.other_profile = ensure_user_profile(cls.other_applicant)
        cls.other_profile.real_name = "타부서"
        cls.other_profile.onboarding_status = UserProfile.OnboardingStatus.PENDING
        cls.other_profile.requested_division = cls.div_c
        cls.other_profile.save()

    def test_applications_page_includes_edit_modal_context(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_onboarding_applications"),
            {"division_code": self.div_a.code},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("application_edit_json", r.context)
        self.assertIn("divisions_map_json", r.context)
        self.assertIn("retreat_events_json", r.context)
        self.assertIn("retreat_groups_json", r.context)
        self.assertContains(r, "applicationEditOverlay")
        self.assertContains(r, "활동 로그")

    def test_update_profile_saves_fields(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            {
                "action": "update_profile",
                "profile_id": str(self.profile.id),
                "real_name": "수정실명",
                "display_name": "수정표시",
                "phone": "01033334444",
                "requested_division_id": str(self.div_a.id),
                "requested_team_id": str(self.team_a2.id),
                "requested_retreat_event_id": str(self.event.id),
                "requested_retreat_group_id": str(self.group.id),
                "division_code": self.div_a.code,
            },
        )
        self.assertEqual(r.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.real_name, "수정실명")
        self.assertEqual(self.profile.display_name, "수정표시")
        self.assertEqual(self.profile.phone, "010-3333-4444")
        self.assertEqual(self.profile.requested_team_id, self.team_a2.id)
        self.assertEqual(self.profile.requested_retreat_group_id, self.group.id)

    def test_update_profile_rejects_out_of_scope_division(self):
        self.client.force_login(self.manager)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            {
                "action": "update_profile",
                "profile_id": str(self.other_profile.id),
                "real_name": "해킹",
                "display_name": "",
                "phone": "",
                "requested_division_id": str(self.div_c.id),
                "division_code": "__all__",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.other_profile.refresh_from_db()
        self.assertEqual(self.other_profile.real_name, "타부서")

    def test_activity_log_ok_for_allowed_profile(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_onboarding_application_activity_log"),
            {"profile_id": str(self.profile.id)},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("items", data)
        self.assertTrue(len(data["items"]) >= 1)

    def test_activity_log_forbidden_for_out_of_scope_profile(self):
        self.client.force_login(self.manager)
        r = self.client.get(
            reverse("user_onboarding_application_activity_log"),
            {"profile_id": str(self.other_profile.id)},
        )
        self.assertEqual(r.status_code, 403)


class DivisionAccountActivityLogTests(AccountManageFixture):
    def test_roles_page_includes_signup_application_in_account_details(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("user_division_account_roles"),
            {"division_code": self.div_a.code},
        )
        self.assertEqual(r.status_code, 200)
        details = json.loads(r.context["account_details_json"])
        member_detail = details[str(self.member.id)]
        signup = member_detail["signup_application"]
        self.assertTrue(signup["has_application"])
        self.assertEqual(signup["division_name"], self.div_a.name)
        self.assertEqual(signup["team_name"], self.team_a.name)
        self.assertEqual(signup["applicant_role_label"], "성도")
        self.assertFalse(signup["is_pastoral_applicant"])
        self.assertContains(r, "accountSignupApplicationSection")
        self.assertContains(r, "가입 신청 정보")

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
