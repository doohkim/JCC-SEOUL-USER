"""가입신청(온보딩) 폼 검증."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from retreat.models import RetreatEvent
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
            "gender": UserProfile.Gender.MALE,
            "requested_region": str(self.region.id),
            "requested_division": str(self.division.id),
            "requested_team": "",
            "requested_applicant_role": UserProfile.ApplicantRole.MEMBER,
        }

    def test_signup_succeeds_without_retreat_fields_even_when_flagged(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("user_onboarding"), self._base_payload())
        self.assertEqual(r.status_code, 302)
        self.assertIn("/notices/", r.url)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(
            profile.onboarding_status, UserProfile.OnboardingStatus.APPROVED
        )
        self.assertFalse(profile.requested_retreat_participation)
        self.assertIsNone(profile.requested_retreat_group_id)
        self.assertTrue(
            UserDivisionTeam.objects.filter(
                user=self.user, division=self.division
            ).exists()
        )

    def test_signup_page_does_not_show_retreat_fields(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("user_onboarding"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "수련회 참석")
        self.assertNotContains(r, "수련회 집회")
        self.assertNotContains(r, "수련회 조")

    def test_signup_requires_gender(self):
        self.client.force_login(self.user)
        payload = self._base_payload()
        del payload["gender"]
        r = self.client.post(reverse("user_onboarding"), payload)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "이 필드는 필수 항목입니다")

    def test_signup_saves_gender_on_profile(self):
        self.client.force_login(self.user)
        payload = self._base_payload()
        payload["gender"] = UserProfile.Gender.FEMALE
        r = self.client.post(reverse("user_onboarding"), payload)
        self.assertEqual(r.status_code, 302)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.gender, UserProfile.Gender.FEMALE)

    def test_pastor_signup_clears_team_and_retreat(self):
        self.client.force_login(self.user)
        payload = self._base_payload()
        payload["requested_applicant_role"] = UserProfile.ApplicantRole.PASTOR
        r = self.client.post(reverse("user_onboarding"), payload)
        self.assertEqual(r.status_code, 302)

        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(
            profile.requested_applicant_role, UserProfile.ApplicantRole.PASTOR
        )
        self.assertFalse(profile.requested_retreat_participation)
        self.assertIsNone(profile.requested_retreat_group_id)
        self.assertIsNone(profile.requested_team_id)

    def test_member_default_applicant_role_on_signup(self):
        self.client.force_login(self.user)
        payload = self._base_payload()
        del payload["requested_applicant_role"]
        r = self.client.post(reverse("user_onboarding"), payload)
        self.assertEqual(r.status_code, 302)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(
            profile.requested_applicant_role, UserProfile.ApplicantRole.MEMBER
        )
