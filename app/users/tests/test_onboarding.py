"""가입신청(온보딩) 폼 검증."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from retreat.models import RetreatAttendee, RetreatEvent, RetreatGroup
from users.mixins import ensure_user_profile
from users.models import Division, Region, UserDivisionTeam, UserProfile

User = get_user_model()


class OnboardingRetreatParticipationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.region, name="온보딩청년", code="onboard_youth", sort_order=99
        )
        cls.event = RetreatEvent.objects.create(
            name="2026 여름 수련회",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
            is_active=True,
            require_retreat_participation_on_signup=True,
        )
        cls.user = User.objects.create_user(username="onboard_user", password="x")
        profile = ensure_user_profile(cls.user)
        profile.onboarding_status = UserProfile.OnboardingStatus.REJECTED
        profile.save(update_fields=["onboarding_status", "updated_at"])

    def _base_payload(self):
        return {
            "real_name": "홍길동",
            "phone": "01012345678",
            "requested_region": str(self.region.id),
            "requested_division": str(self.division.id),
            "requested_team": "",
            "requested_applicant_role": UserProfile.ApplicantRole.MEMBER,
            "requested_retreat_role": "participant",
        }

    def test_participation_required_when_active_event_flagged(self):
        self.client.force_login(self.user)
        payload = self._base_payload()
        payload["requested_retreat_participation"] = ""
        r = self.client.post(reverse("user_onboarding"), payload)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "수련회 참석 여부를 선택해 주세요.")

    def test_participation_not_required_without_flagged_event(self):
        self.event.require_retreat_participation_on_signup = False
        self.event.save(update_fields=["require_retreat_participation_on_signup", "updated_at"])
        self.client.force_login(self.user)
        payload = self._base_payload()
        payload["requested_retreat_participation"] = ""
        r = self.client.post(reverse("user_onboarding"), payload)
        self.assertEqual(r.status_code, 302)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.onboarding_status, UserProfile.OnboardingStatus.PENDING)
        self.assertFalse(profile.requested_retreat_participation)

    def test_signup_with_retreat_group_then_approval_creates_linked_attendee(self):
        """가입신청서에서 조 선택 후 승인하면 조원·계정이 연동된다."""
        group = RetreatGroup.objects.create(
            event=self.event,
            region=self.region,
            division=self.division,
            name="온보딩1조",
        )
        staff = User.objects.create_user(username="onboard_staff", password="x", is_staff=True)
        UserDivisionTeam.objects.create(
            user=staff, division=self.division, is_primary=True
        )

        self.client.force_login(self.user)
        payload = self._base_payload()
        payload["requested_retreat_participation"] = "yes"
        payload["requested_retreat_event"] = str(self.event.id)
        payload["requested_retreat_group"] = str(group.id)
        r = self.client.post(reverse("user_onboarding"), payload)
        self.assertEqual(r.status_code, 302)

        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.requested_retreat_participation)
        self.assertEqual(profile.requested_retreat_group_id, group.id)

        self.client.force_login(staff)
        r = self.client.post(
            reverse("user_onboarding_applications"),
            {
                "profile_id": str(profile.id),
                "action": "approve",
                "requested_division_id": str(self.division.id),
            },
        )
        self.assertEqual(r.status_code, 302)
        attendee = RetreatAttendee.objects.get(group=group, user=self.user)
        self.assertEqual(attendee.name, "홍길동")
        self.assertEqual(attendee.user_id, self.user.id)

    def test_pastor_signup_skips_retreat_and_does_not_require_participation(self):
        self.client.force_login(self.user)
        group = RetreatGroup.objects.create(
            event=self.event,
            region=self.region,
            division=self.division,
            name="목회자조",
        )
        payload = self._base_payload()
        payload["requested_applicant_role"] = UserProfile.ApplicantRole.PASTOR
        payload["requested_retreat_participation"] = "yes"
        payload["requested_retreat_event"] = str(self.event.id)
        payload["requested_retreat_group"] = str(group.id)
        r = self.client.post(reverse("user_onboarding"), payload)
        self.assertEqual(r.status_code, 302)

        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.requested_applicant_role, UserProfile.ApplicantRole.PASTOR)
        self.assertFalse(profile.requested_retreat_participation)
        self.assertIsNone(profile.requested_retreat_group_id)
        self.assertIsNone(profile.requested_team_id)

    def test_member_default_applicant_role_on_signup(self):
        self.event.require_retreat_participation_on_signup = False
        self.event.save(update_fields=["require_retreat_participation_on_signup", "updated_at"])
        self.client.force_login(self.user)
        payload = self._base_payload()
        del payload["requested_applicant_role"]
        r = self.client.post(reverse("user_onboarding"), payload)
        self.assertEqual(r.status_code, 302)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.requested_applicant_role, UserProfile.ApplicantRole.MEMBER)
