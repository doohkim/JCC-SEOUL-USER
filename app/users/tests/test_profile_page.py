"""내 프로필 페이지."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from users.mixins import ensure_user_profile
from users.models import Division, Region, Team, UserDivisionTeam, UserProfile

User = get_user_model()


class UserProfilePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.seoul, code="profile_div", name="청년부", sort_order=99
        )
        cls.team = Team.objects.create(
            division=cls.division, code="profile_team", name="1팀", sort_order=1
        )
        cls.user = User.objects.create_user(username="profile_user", password="x")
        profile = ensure_user_profile(cls.user)
        profile.real_name = "홍길동"
        profile.phone = "01012345678"
        profile.bio = "안녕하세요"
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.save()
        UserDivisionTeam.objects.create(
            user=cls.user,
            division=cls.division,
            team=cls.team,
            is_primary=True,
        )

    def setUp(self):
        self.client = Client()
        self.url = reverse("user_profile")

    def test_anonymous_redirects_to_login(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r.url)

    def test_authenticated_get_ok(self):
        self.client.force_login(self.user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "내 프로필")
        self.assertContains(r, "홍길동")
        self.assertContains(r, "청년부")
        self.assertNotContains(r, "표시 이름")
        self.assertContains(r, "실명")

    def test_post_updates_profile(self):
        self.client.force_login(self.user)
        r = self.client.post(
            self.url,
            {
                "real_name": "김샬롬",
                "phone": "010-9876-5432",
                "bio": "수정된 소개",
                "interest_topics": "찬양, 봉사",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, self.url)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.real_name, "김샬롬")
        self.assertEqual(profile.phone, "010-9876-5432")
        self.assertEqual(profile.bio, "수정된 소개")
        self.assertEqual(profile.interest_topics, "찬양,봉사")

    def test_post_normalizes_interest_topics(self):
        self.client.force_login(self.user)
        r = self.client.post(
            self.url,
            {
                "real_name": "홍길동",
                "phone": "010-1234-5678",
                "bio": "",
                "interest_topics": "#찬양, 찬양, 모티스락",
            },
        )
        self.assertEqual(r.status_code, 302)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.interest_topics, "찬양,모티스락")
