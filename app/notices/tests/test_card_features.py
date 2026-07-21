"""공지 카드형 UI: 카테고리·검색·조회수·API."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from notices.models import Notice, NoticeCategory
from notices.services.newness import has_notices_created_today, is_created_today
from users.models import Division, Region, UserProfile

User = get_user_model()

_STATIC_STORAGE = override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)


@_STATIC_STORAGE
class NoticeCardFeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="card_test_div", name="카드테스트부"
        )
        cls.user = User.objects.create_superuser(username="card_super", password="x")
        cls.cat_spiritual = NoticeCategory.objects.create(
            name="영성", slug="spiritual", color="#4a9eff", sort_order=1
        )
        cls.cat_logistics = NoticeCategory.objects.create(
            name="진행", slug="logistics", color="#f5a623", sort_order=2
        )
        cls.notice_a = Notice.objects.create(
            title="영성 공지",
            body="영성 본문 내용입니다.",
            category=cls.cat_spiritual,
            tags="수련회, 청년부",
            created_by=cls.user,
        )
        cls.notice_b = Notice.objects.create(
            title="진행 안내",
            body="진행 관련 안내입니다.",
            category=cls.cat_logistics,
            created_by=cls.user,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_category_api_returns_active_categories(self):
        NoticeCategory.objects.create(name="비활성", slug="inactive", is_active=False)
        r = self.client.get(reverse("notice_category_list_api"))
        self.assertEqual(r.status_code, 200)
        slugs = [item["slug"] for item in r.json()]
        self.assertIn("spiritual", slugs)
        self.assertIn("logistics", slugs)
        self.assertNotIn("inactive", slugs)

    def test_list_filters_by_category_slug(self):
        r = self.client.get(reverse("notice_list"), {"category": "spiritual"})
        self.assertEqual(r.status_code, 200)
        titles = [n.title for n in r.context["notices"]]
        self.assertEqual(titles, ["영성 공지"])

    def test_list_search_by_title_or_body(self):
        r = self.client.get(reverse("notice_list"), {"q": "진행 관련"})
        self.assertEqual(r.status_code, 200)
        titles = [n.title for n in r.context["notices"]]
        self.assertEqual(titles, ["진행 안내"])

    def test_detail_increments_view_count(self):
        notice = Notice.objects.get(pk=self.notice_a.pk)
        self.assertEqual(notice.view_count, 0)
        r = self.client.get(reverse("notice_detail", args=[notice.pk]))
        self.assertEqual(r.status_code, 200)
        notice.refresh_from_db()
        self.assertEqual(notice.view_count, 1)
        self.assertIn("수련회", r.context["notice"].tag_list)

    def test_list_renders_card_grid_markup(self):
        r = self.client.get(reverse("notice_list"))
        self.assertContains(r, "jcc-notice-cardGrid")
        self.assertContains(r, "jcc-notice-cardTitle")
        self.assertContains(r, "jcc-leftNav-newBadge")

    def test_detail_renders_banner_and_tags(self):
        r = self.client.get(reverse("notice_detail", args=[self.notice_a.pk]))
        self.assertContains(r, "jcc-notice-detailBanner")
        self.assertContains(r, "#수련회")
        self.assertContains(r, "jcc-notice-detailNav")

    def test_anonymous_cannot_access_category_api(self):
        self.client.logout()
        r = self.client.get(reverse("notice_category_list_api"))
        self.assertEqual(r.status_code, 403)

    def test_is_new_is_same_calendar_day(self):
        self.assertTrue(is_created_today(self.notice_a.created_at))
        Notice.objects.filter(pk=self.notice_a.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        self.notice_a.refresh_from_db()
        self.assertFalse(is_created_today(self.notice_a.created_at))

    def test_nav_shows_new_badge_when_notice_created_today(self):
        r = self.client.get(reverse("notice_list"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(has_notices_created_today())
        self.assertContains(r, "jcc-leftNav-newBadge")
        self.assertContains(r, "오늘 새 이야기")

    def test_nav_hides_new_badge_when_no_notice_today(self):
        Notice.objects.all().update(created_at=timezone.now() - timedelta(days=1))
        self.assertFalse(has_notices_created_today())
        r = self.client.get(reverse("notice_list"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "jcc-leftNav-newBadge")

    def test_api_is_new_matches_same_day(self):
        r = self.client.get(reverse("notice_list_api"))
        self.assertEqual(r.status_code, 200)
        results = r.json()["results"]
        by_title = {item["title"]: item["is_new"] for item in results}
        self.assertTrue(by_title["영성 공지"])
        Notice.objects.filter(pk=self.notice_a.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        r2 = self.client.get(reverse("notice_list_api"))
        by_title2 = {item["title"]: item["is_new"] for item in r2.json()["results"]}
        self.assertFalse(by_title2["영성 공지"])
