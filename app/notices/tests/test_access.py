"""공지·타임테이블 접근 권한 테스트."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from users.models import Division, Region, UserProfile

User = get_user_model()


class _NoticeAccessFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="notice_test_div", name="공지테스트부"
        )
        cls.superuser = User.objects.create_superuser(
            username="notice_super", password="x"
        )
        cls.pending_user = User.objects.create_user(
            username="notice_pending", password="x"
        )
        cls.pending_profile = UserProfile.objects.create(
            user=cls.pending_user,
            onboarding_status=UserProfile.OnboardingStatus.PENDING,
            requested_division=cls.div,
        )
        cls.approved_user = User.objects.create_user(
            username="notice_approved", password="x"
        )
        cls.approved_profile = UserProfile.objects.create(
            user=cls.approved_user,
            onboarding_status=UserProfile.OnboardingStatus.APPROVED,
            requested_division=cls.div,
        )
        cls.rejected_user = User.objects.create_user(
            username="notice_rejected", password="x"
        )
        cls.rejected_profile = UserProfile.objects.create(
            user=cls.rejected_user,
            onboarding_status=UserProfile.OnboardingStatus.REJECTED,
            requested_division=cls.div,
        )
        cls.unsubmitted_user = User.objects.create_user(
            username="notice_unsubmitted", password="x"
        )
        UserProfile.objects.create(
            user=cls.unsubmitted_user,
            onboarding_status=UserProfile.OnboardingStatus.PENDING,
        )

    def setUp(self):
        self.client = Client()


class NoticeAccessTests(_NoticeAccessFixture):
    """개발 단계: 공지/타임테이블은 superuser 전용."""

    def test_anonymous_redirects_to_login(self):
        r = self.client.get(reverse("notice_list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r.url)

    def test_superuser_can_list(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("notice_list"))
        self.assertEqual(r.status_code, 200)

    def test_pending_forbidden(self):
        self.client.force_login(self.pending_user)
        self.assertEqual(self.client.get(reverse("notice_list")).status_code, 403)

    def test_approved_forbidden(self):
        self.client.force_login(self.approved_user)
        self.assertEqual(self.client.get(reverse("notice_list")).status_code, 403)

    def test_rejected_forbidden(self):
        self.client.force_login(self.rejected_user)
        self.assertEqual(self.client.get(reverse("notice_list")).status_code, 403)

    def test_timetable_superuser_only(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(reverse("timetable")).status_code, 200)
        self.client.force_login(self.approved_user)
        self.assertEqual(self.client.get(reverse("timetable")).status_code, 403)
        self.client.logout()
        r = self.client.get(reverse("timetable"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r.url)


class TimetableEventTests(_NoticeAccessFixture):
    """타임테이블 탭이 수련회 행사별 일정을 행사 드롭다운으로 보여준다."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from datetime import date

        from retreat.models import RetreatEvent, RetreatTimetableEntry

        cls.event = RetreatEvent.objects.create(
            name="2026 수련회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
        )
        RetreatTimetableEntry.objects.create(
            event=cls.event,
            day=date(2026, 7, 1),
            start_time="09:00",
            title="개회 예배",
            location="본당",
        )

    def test_timetable_lists_event_and_entries(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("timetable"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["selected_event"].id, self.event.id)
        self.assertContains(r, "개회 예배")
        self.assertContains(r, 'id="ttEventSelect"')

    def test_timetable_respects_event_query(self):
        from datetime import date

        from retreat.models import RetreatEvent

        other = RetreatEvent.objects.create(
            name="2025 수련회",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 2),
        )
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("timetable"), {"event": other.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["selected_event"].id, other.id)
        self.assertNotContains(r, "개회 예배")


class NoticeWriteAccessTests(_NoticeAccessFixture):
    def test_superuser_can_open_create_form(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("notice_create"))
        self.assertEqual(r.status_code, 200)

    def test_superuser_can_create_notice(self):
        self.client.force_login(self.superuser)
        r = self.client.post(
            reverse("notice_create"),
            {"title": "테스트 공지", "body": "내용", "is_pinned": False, "scope": "all"},
        )
        self.assertEqual(r.status_code, 302)
        from notices.models import Notice

        self.assertTrue(Notice.objects.filter(title="테스트 공지").exists())

    def test_pending_user_cannot_create(self):
        self.client.force_login(self.pending_user)
        r = self.client.get(reverse("notice_create"))
        self.assertEqual(r.status_code, 403)

    def test_approved_user_cannot_create(self):
        self.client.force_login(self.approved_user)
        r = self.client.get(reverse("notice_create"))
        self.assertEqual(r.status_code, 403)


class NoticeScopeTests(_NoticeAccessFixture):
    """전체/지역·부서 대상 공지의 생성·가시성 규칙."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_div = Division.objects.create(
            region=cls.seoul, code="notice_other_div", name="다른부서"
        )

    def test_create_division_notice_requires_division(self):
        self.client.force_login(self.superuser)
        r = self.client.post(
            reverse("notice_create"),
            {"title": "부서공지", "body": "내용", "scope": "division"},
        )
        self.assertEqual(r.status_code, 200)  # 폼 재표시(검증 실패)
        self.assertFalse(self.notice_model().objects.filter(title="부서공지").exists())

    def test_create_division_notice_with_division(self):
        self.client.force_login(self.superuser)
        r = self.client.post(
            reverse("notice_create"),
            {
                "title": "부서공지",
                "body": "내용",
                "scope": "division",
                "division": self.div.id,
            },
        )
        self.assertEqual(r.status_code, 302)
        notice = self.notice_model().objects.get(title="부서공지")
        self.assertEqual(notice.scope, "division")
        self.assertEqual(notice.division_id, self.div.id)

    def test_all_scope_clears_division(self):
        self.client.force_login(self.superuser)
        self.client.post(
            reverse("notice_create"),
            {
                "title": "전체공지",
                "body": "내용",
                "scope": "all",
                "division": self.div.id,
            },
        )
        notice = self.notice_model().objects.get(title="전체공지")
        self.assertIsNone(notice.division_id)

    def test_visible_queryset_division_filter(self):
        Notice = self.notice_model()
        all_n = Notice.objects.create(title="전체", body="x", scope="all")
        my_n = Notice.objects.create(
            title="우리부서", body="x", scope="division", division=self.div
        )
        other_n = Notice.objects.create(
            title="다른부서", body="x", scope="division", division=self.other_div
        )
        ids = set(
            Notice.visible_queryset(division_id=self.div.id).values_list(
                "id", flat=True
            )
        )
        self.assertIn(all_n.id, ids)
        self.assertIn(my_n.id, ids)
        self.assertNotIn(other_n.id, ids)

    def test_list_filter_by_division(self):
        Notice = self.notice_model()
        Notice.objects.create(title="전체", body="x", scope="all")
        Notice.objects.create(
            title="우리부서", body="x", scope="division", division=self.div
        )
        Notice.objects.create(
            title="다른부서", body="x", scope="division", division=self.other_div
        )
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("notice_list"), {"division": self.div.id})
        titles = {n.title for n in r.context["notices"]}
        self.assertEqual(titles, {"전체", "우리부서"})

    @staticmethod
    def notice_model():
        from notices.models import Notice

        return Notice
