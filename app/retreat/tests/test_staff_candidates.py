"""집회 운영진 배정 대기 후보 API 테스트."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from retreat.models import (
    RetreatCouncilMembership,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatGroupScope,
    RetreatStaffApplication,
)
from retreat.tests.fixtures.council_matrix_fixture import CouncilMatrixFixture
from users.mixins import ensure_user_profile
from users.models import Division, UserDivisionTeam, UserProfile

User = get_user_model()


class StaffCandidatesApiTests(CouncilMatrixFixture):
    def setUp(self):
        super().setUp()
        self.auth_as(self.event_admin)
        self.url = reverse("api_retreat_event_staff_candidates", args=[self.event.id])
        profile = ensure_user_profile(self.link_user)
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.real_name = "배정대기"
        profile.save(update_fields=["onboarding_status", "real_name", "updated_at"])
        UserDivisionTeam.objects.create(
            user=self.link_user, division=self.div_seoul, is_primary=True
        )

    def _approved_application(self, **kwargs):
        defaults = {
            "event": self.event,
            "user": self.link_user,
            "region": self.group_seoul.region,
            "division": self.group_seoul.division,
            "group": self.group_seoul,
            "group_role": RetreatGroupMembership.Role.LEADER,
            "status": RetreatStaffApplication.Status.APPROVED,
        }
        defaults.update(kwargs)
        return RetreatStaffApplication.objects.create(**defaults)

    def test_lists_approved_applicants_not_yet_staff(self):
        self._approved_application()
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        user_ids = {row["user_id"] for row in r.json()}
        self.assertIn(self.link_user.id, user_ids)
        row = next(row for row in r.json() if row["user_id"] == self.link_user.id)
        self.assertEqual(row["group_id"], self.group_seoul.id)
        self.assertEqual(row["group_name"], self.group_seoul.name)
        self.assertEqual(row["name"], "배정대기")

    def test_excludes_pending_applications(self):
        RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.link_user,
            region=self.group_seoul.region,
            division=self.group_seoul.division,
            group=self.group_seoul,
            group_role=RetreatGroupMembership.Role.LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.link_user.id, {row["user_id"] for row in r.json()})

    def test_excludes_council_members(self):
        self._approved_application()
        RetreatCouncilMembership.objects.create(
            event=self.event,
            user=self.link_user,
            role=RetreatCouncilMembership.Role.EVENT_OBSERVER,
        )
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.link_user.id, {row["user_id"] for row in r.json()})

    def test_excludes_group_leaders(self):
        self._approved_application()
        RetreatGroupMembership.objects.create(
            group=self.group_seoul,
            user=self.link_user,
            role=RetreatGroupMembership.Role.LEADER,
        )
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.link_user.id, {row["user_id"] for row in r.json()})

    def test_excludes_retired_users(self):
        self._approved_application()
        self.link_user.is_active = False
        self.link_user.retired_at = timezone.now()
        self.link_user.save(update_fields=["is_active", "retired_at"])
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.link_user.id, {row["user_id"] for row in r.json()})

    def test_observer_can_view_candidates(self):
        self._approved_application()
        self.auth_as(self.event_observer)
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_unauthorized_user_denied(self):
        outsider = self._council_user(
            "cm_outsider_other_event",
            RetreatCouncilMembership.Role.EVENT_ADMIN,
        )
        RetreatCouncilMembership.objects.filter(
            user=outsider, event=self.event
        ).delete()
        RetreatCouncilMembership.objects.create(
            event=self.other_event,
            user=outsider,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )
        self.auth_as(outsider)
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 403)


class UserSearchStaffPoolTests(CouncilMatrixFixture):
    def setUp(self):
        super().setUp()
        self.auth_as(self.event_admin)
        self.search_url = reverse("api_retreat_user_search")
        profile = ensure_user_profile(self.link_user)
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.save(update_fields=["onboarding_status", "updated_at"])
        UserDivisionTeam.objects.create(
            user=self.link_user, division=self.div_seoul, is_primary=True
        )

    def test_staff_pool_lists_event_division_members(self):
        r = self.api.get(
            self.search_url,
            {"event_id": self.event.id, "staff_pool": "1"},
        )
        self.assertEqual(r.status_code, 200)
        user_ids = {row["id"] for row in r.json()}
        self.assertIn(self.link_user.id, user_ids)

    def test_staff_pool_excludes_division_without_event_group(self):
        other_div = Division.objects.create(
            region=self.seoul, code="cm_pool_other_div", name="미배정부서"
        )
        other_div_user = User.objects.create_user(
            username="cm_pool_other_div", password="x"
        )
        UserDivisionTeam.objects.create(
            user=other_div_user, division=other_div, is_primary=True
        )
        profile = ensure_user_profile(other_div_user)
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.save(update_fields=["onboarding_status", "updated_at"])
        r = self.api.get(
            self.search_url,
            {"event_id": self.event.id, "staff_pool": "1"},
        )
        self.assertEqual(r.status_code, 200)
        user_ids = {row["id"] for row in r.json()}
        self.assertIn(self.link_user.id, user_ids)
        self.assertNotIn(other_div_user.id, user_ids)

    def test_staff_pool_includes_user_without_staff_application(self):
        """참가 신청 없이도 집회 조 부서 소속이면 검색 풀에 포함."""
        r = self.api.get(
            self.search_url,
            {"event_id": self.event.id, "staff_pool": "1", "q": self.link_user.username},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.link_user.id, {row["id"] for row in r.json()})
        self.assertFalse(
            RetreatStaffApplication.objects.filter(
                event=self.event, user=self.link_user
            ).exists()
        )

    def test_staff_pool_includes_extra_scope_division(self):
        extra_div = Division.objects.create(
            region=self.seoul, code="cm_pool_extra_div", name="보조부서"
        )
        RetreatGroupScope.objects.create(
            group=self.group_seoul,
            region=self.seoul,
            division=extra_div,
        )
        extra_user = User.objects.create_user(username="cm_pool_extra", password="x")
        UserDivisionTeam.objects.create(
            user=extra_user, division=extra_div, is_primary=True
        )
        profile = ensure_user_profile(extra_user)
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.save(update_fields=["onboarding_status", "updated_at"])
        r = self.api.get(
            self.search_url,
            {"event_id": self.event.id, "staff_pool": "1", "q": extra_user.username},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(extra_user.id, {row["id"] for row in r.json()})

    def test_staff_pool_excludes_already_assigned_users(self):
        RetreatGroupMembership.objects.create(
            group=self.group_seoul,
            user=self.link_user,
            role=RetreatGroupMembership.Role.LEADER,
        )
        r = self.api.get(
            self.search_url,
            {"event_id": self.event.id, "staff_pool": "1", "q": self.link_user.username},
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.link_user.id, {row["id"] for row in r.json()})

    def test_staff_pool_excludes_retired_users(self):
        self.link_user.is_active = False
        self.link_user.retired_at = timezone.now()
        self.link_user.save(update_fields=["is_active", "retired_at"])
        r = self.api.get(
            self.search_url,
            {"event_id": self.event.id, "staff_pool": "1", "q": self.link_user.username},
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.link_user.id, {row["id"] for row in r.json()})

    def test_event_id_without_staff_pool_still_uses_attendees(self):
        from retreat.models import RetreatAttendee

        RetreatAttendee.objects.create(
            group=self.group_seoul,
            user=self.link_user,
            name="집회조원",
        )
        r = self.api.get(
            self.search_url,
            {"event_id": self.event.id, "q": self.link_user.username},
        )
        self.assertEqual(r.status_code, 200)
        usernames = {row["username"] for row in r.json()}
        self.assertIn(self.link_user.username, usernames)
