"""집회당 user → 조원 1행 정리·프로필 동기화 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
from retreat.services.onboarding import apply_retreat_membership_on_approval
from users.models import Division, Region, UserProfile

User = get_user_model()


class _AttendeeDedupFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="dedup_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="중복 정리 집회",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.group1 = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.group2 = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="2조",
        )
        cls.council = User.objects.create_user(username="dedup_council", password="x")
        cls.leader2 = User.objects.create_user(username="dedup_leader2", password="x")
        RetreatGroupMembership.objects.create(
            user=cls.leader2,
            group=cls.group2,
            role=RetreatGroupMembership.Role.LEADER,
        )


class AttendeeDedupOnboardingTests(_AttendeeDedupFixture):
    def test_onboarding_then_leader_in_other_group_removes_stale_attendee(self):
        """김필중 시나리오: 1조 온보딩 후 2조 조장 지정 시 1조 행 제거."""
        applicant = User.objects.create_user(username="dedup_kim", password="x")
        profile = UserProfile.objects.create(
            user=applicant,
            real_name="김필중",
            requested_retreat_participation=True,
            requested_retreat_event=self.event,
            requested_retreat_group=self.group1,
            requested_retreat_role="participant",
        )
        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group1.id),
            retreat_role="participant",
            changed_by=self.council,
            appoint_leadership=False,
        )
        self.assertTrue(
            RetreatAttendee.objects.filter(group=self.group1, user=applicant).exists()
        )

        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group2.id),
            retreat_role="leader",
            changed_by=self.council,
            appoint_leadership=True,
        )

        self.assertFalse(
            RetreatAttendee.objects.filter(group=self.group1, user=applicant).exists()
        )
        attendee = RetreatAttendee.objects.get(group=self.group2, user=applicant)
        self.assertEqual(attendee.member_role, RetreatAttendee.MemberRole.LEADER)
        self.assertEqual(
            RetreatAttendee.objects.filter(
                user=applicant, group__event=self.event
            ).count(),
            1,
        )

    def test_onboarding_sets_lodging_stay_status(self):
        applicant = User.objects.create_user(username="dedup_stay", password="x")
        profile = UserProfile.objects.create(
            user=applicant,
            requested_retreat_participation=True,
            requested_retreat_event=self.event,
            requested_retreat_group=self.group1,
        )
        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group1.id),
            retreat_role="participant",
            changed_by=self.council,
            appoint_leadership=False,
        )
        attendee = RetreatAttendee.objects.get(group=self.group1, user=applicant)
        self.assertIsNotNone(attendee.lodging_stay_status)
        self.assertEqual(
            attendee.lodging_stay_status,
            RetreatAttendee.LodgingStayStatus.NO_STAY,
        )

    def test_consolidate_does_not_mirror_profile_requested_retreat_group(self):
        applicant = User.objects.create_user(username="dedup_profile", password="x")
        profile = UserProfile.objects.create(
            user=applicant,
            requested_retreat_participation=True,
            requested_retreat_event=self.event,
            requested_retreat_group=self.group1,
        )
        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group1.id),
            retreat_role="participant",
            changed_by=self.council,
            appoint_leadership=False,
        )
        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group2.id),
            retreat_role="leader",
            changed_by=self.council,
            appoint_leadership=True,
        )
        profile.refresh_from_db()
        self.assertEqual(profile.requested_retreat_group_id, self.group1.id)
        self.assertTrue(
            RetreatAttendee.objects.filter(
                group=self.group2, user=applicant, member_role="leader"
            ).exists()
        )


class AttendeeDedupMembershipApiTests(_AttendeeDedupFixture):
    def setUp(self):
        self.client = APIClient()

    def test_membership_api_removes_attendee_in_other_group(self):
        target = User.objects.create_user(username="dedup_api", password="x")
        UserProfile.objects.create(
            user=target,
            requested_retreat_participation=True,
            requested_retreat_event=self.event,
            requested_retreat_group=self.group1,
        )
        apply_retreat_membership_on_approval(
            user=target,
            profile=target.profile,
            retreat_group_id=str(self.group1.id),
            retreat_role="participant",
            changed_by=self.council,
            appoint_leadership=False,
        )
        self.client.force_authenticate(self.leader2)
        url = reverse("api_retreat_group_memberships", args=[self.group2.id])
        r = self.client.post(
            url, {"user_id": target.id, "role": "leader"}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertFalse(
            RetreatAttendee.objects.filter(group=self.group1, user=target).exists()
        )
        self.assertTrue(
            RetreatAttendee.objects.filter(
                group=self.group2, user=target, member_role="leader"
            ).exists()
        )
