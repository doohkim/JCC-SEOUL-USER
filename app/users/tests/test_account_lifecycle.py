"""계정 탈퇴(데이터 보존) 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from retreat.models import (
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
from users.mixins import ensure_user_profile
from users.models import Division, Region, UserDivisionTeam, UserProfile
from users.models.organization import Team
from users.services.account_lifecycle import retire_user

User = get_user_model()


class AccountRetireFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="retire_div", name="청년부"
        )
        cls.team = Team.objects.create(
            division=cls.div, code="retire_t1", name="1팀", sort_order=1
        )
        cls.superuser = User.objects.create_superuser(
            username="retire_super", password="x"
        )
        cls.manager = User.objects.create_user(username="retire_mgr", password="x")
        cls.manager.can_manage_accounts = True
        cls.manager.save()
        UserDivisionTeam.objects.create(
            user=cls.manager, division=cls.div, team=cls.team, is_primary=True
        )

        cls.target = User.objects.create_user(
            username="kakao_9990001", password="x", signup_source=User.SignupSource.KAKAO
        )
        cls.profile = ensure_user_profile(cls.target)
        cls.profile.real_name = "김테스트"
        cls.profile.phone = "01099998888"
        cls.profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        cls.profile.requested_division = cls.div
        cls.profile.save()
        UserDivisionTeam.objects.create(
            user=cls.target, division=cls.div, team=cls.team, is_primary=True
        )

        cls.event = RetreatEvent.objects.create(
            name="탈퇴 테스트 수련회",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
            is_active=True,
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.attendee = RetreatAttendee.objects.create(
            group=cls.group,
            user=cls.target,
            name="김테스트",
            phone="01099998888",
            member_role=RetreatAttendee.MemberRole.LEADER,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        RetreatGroupMembership.objects.create(
            user=cls.target,
            group=cls.group,
            role=RetreatGroupMembership.Role.LEADER,
        )

        cls.orphan = UserProfile.objects.create(
            display_name="고아",
            real_name="고아실명",
            onboarding_status=UserProfile.OnboardingStatus.APPROVED,
            requested_division=cls.div,
        )

    def setUp(self):
        self.client = Client()


class RetireUserTests(AccountRetireFixture):
    def test_retire_preserves_user_row_and_orphans_profile(self):
        pk = self.target.pk
        retire_user(self.target)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertIsNotNone(self.target.retired_at)
        self.assertTrue(self.target.username.startswith(f"retired_{pk}_"))
        self.assertTrue(User.objects.filter(pk=pk).exists())
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.user_id)

    def test_retire_preserves_attendee_detaches_user(self):
        attendee_id = self.attendee.id
        retire_user(self.target)
        attendee = RetreatAttendee.objects.get(pk=attendee_id)
        self.assertIsNone(attendee.user_id)
        self.assertEqual(attendee.name, "김테스트")
        self.assertEqual(attendee.member_role, RetreatAttendee.MemberRole.MEMBER)

    def test_retire_removes_group_membership(self):
        retire_user(self.target)
        self.assertFalse(
            RetreatGroupMembership.objects.filter(user_id=self.target.pk).exists()
        )

    def test_retire_removes_division_team(self):
        retire_user(self.target)
        self.assertFalse(
            UserDivisionTeam.objects.filter(user_id=self.target.pk).exists()
        )

    def test_superuser_cannot_retire(self):
        with self.assertRaises(ValueError):
            retire_user(self.superuser)


class ApprovalListHideTests(AccountRetireFixture):
    def test_orphan_profile_hidden_from_approvals(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("user_account_approvals"))
        self.assertEqual(r.status_code, 200)
        profile_ids = set()
        for key in ("pending_profiles", "approved_profiles", "rejected_profiles"):
            profile_ids.update(r.context[key].values_list("id", flat=True))
        self.assertNotIn(self.orphan.id, profile_ids)

    def test_retired_user_profile_hidden_from_approvals(self):
        retire_user(self.target)
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("user_account_approvals"))
        self.assertEqual(r.status_code, 200)
        profile_ids = set()
        for key in ("pending_profiles", "approved_profiles", "rejected_profiles"):
            profile_ids.update(r.context[key].values_list("id", flat=True))
        self.assertNotIn(self.profile.id, profile_ids)
