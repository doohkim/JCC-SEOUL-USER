"""함께보기 FAQ 탭 접근·활성 노출·슈퍼유저 CRUD 테스트."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from notices.models import FaqItem
from users.models import Division, Region, UserDivisionTeam, UserProfile

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
class FaqAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="faq_test_div", name="FAQ테스트부"
        )
        cls.superuser = User.objects.create_superuser(
            username="faq_super", password="x"
        )
        cls.staff_user = User.objects.create_user(
            username="faq_staff", password="x", is_staff=True
        )
        UserProfile.objects.create(
            user=cls.staff_user,
            onboarding_status=UserProfile.OnboardingStatus.APPROVED,
            requested_division=cls.div,
        )
        cls.approved_user = User.objects.create_user(
            username="faq_approved", password="x"
        )
        UserProfile.objects.create(
            user=cls.approved_user,
            onboarding_status=UserProfile.OnboardingStatus.APPROVED,
            requested_division=cls.div,
        )
        UserDivisionTeam.objects.create(
            user=cls.approved_user,
            division=cls.div,
            is_primary=True,
        )
        cls.pending_user = User.objects.create_user(
            username="faq_pending", password="x"
        )
        UserProfile.objects.create(
            user=cls.pending_user,
            onboarding_status=UserProfile.OnboardingStatus.PENDING,
            requested_division=cls.div,
        )
        cls.active_faq = FaqItem.objects.create(
            question="함께보기는 무엇인가요?",
            answer="공지와 일정을 함께 보는 공간입니다.",
            sort_order=1,
            is_active=True,
        )
        cls.inactive_faq = FaqItem.objects.create(
            question="숨겨진 질문",
            answer="보이지 않아야 합니다.",
            sort_order=2,
            is_active=False,
        )

    def setUp(self):
        self.client = Client()

    def test_anonymous_redirects_to_login(self):
        r = self.client.get(reverse("notice_faq"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r.url)

    def test_pending_redirected_to_onboarding(self):
        self.client.force_login(self.pending_user)
        r = self.client.get(reverse("notice_faq"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/onboarding", r.url)

    def test_approved_can_view_faq_page(self):
        self.client.force_login(self.approved_user)
        r = self.client.get(reverse("notice_faq"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["notices_tab"], "faq")
        self.assertFalse(r.context["can_manage_faq"])
        self.assertContains(r, "함께보기는 무엇인가요?")
        self.assertContains(r, "공지와 일정을 함께 보는 공간입니다.")
        self.assertNotContains(r, "숨겨진 질문")
        self.assertContains(r, 'href="/faq/"')
        self.assertContains(r, "jcc-notice-faqItem")
        self.assertNotContains(r, "FAQ 작성")
        self.assertNotContains(r, reverse("notice_faq_create"))

    def test_only_active_faqs_in_context(self):
        self.client.force_login(self.approved_user)
        r = self.client.get(reverse("notice_faq"))
        faqs = list(r.context["faqs"])
        self.assertEqual(faqs, [self.active_faq])

    def test_subtabs_and_bottom_tabs_include_faq(self):
        self.client.force_login(self.approved_user)
        r = self.client.get(reverse("notice_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, reverse("notice_faq"))
        self.assertContains(r, ">FAQ<")

    def test_superuser_sees_inactive_and_manage_ui(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("notice_faq"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_faq"])
        self.assertContains(r, "숨겨진 질문")
        self.assertContains(r, "비활성")
        self.assertContains(r, reverse("notice_faq_create"))
        self.assertContains(r, reverse("notice_faq_edit", args=[self.active_faq.pk]))
        self.assertContains(r, reverse("notice_faq_delete", args=[self.active_faq.pk]))
        self.assertEqual(set(r.context["faqs"]), {self.active_faq, self.inactive_faq})

    def test_superuser_can_create_faq(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("notice_faq_create"))
        self.assertEqual(r.status_code, 200)
        r2 = self.client.post(
            reverse("notice_faq_create"),
            {
                "question": "로그인 방법은?",
                "answer": "카카오로 로그인합니다.",
                "sort_order": 3,
                "is_active": "on",
            },
        )
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(r2.url, reverse("notice_faq"))
        self.assertTrue(FaqItem.objects.filter(question="로그인 방법은?").exists())

    def test_superuser_can_edit_faq(self):
        self.client.force_login(self.superuser)
        r = self.client.post(
            reverse("notice_faq_edit", args=[self.active_faq.pk]),
            {
                "question": "함께보기는 무엇인가요? (수정)",
                "answer": "수정된 답변입니다.",
                "sort_order": 1,
                "is_active": "on",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.active_faq.refresh_from_db()
        self.assertEqual(self.active_faq.question, "함께보기는 무엇인가요? (수정)")
        self.assertEqual(self.active_faq.answer, "수정된 답변입니다.")

    def test_superuser_can_delete_faq(self):
        self.client.force_login(self.superuser)
        pk = self.active_faq.pk
        r = self.client.post(reverse("notice_faq_delete", args=[pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(FaqItem.objects.filter(pk=pk).exists())

    def test_approved_cannot_manage_faq(self):
        self.client.force_login(self.approved_user)
        self.assertEqual(self.client.get(reverse("notice_faq_create")).status_code, 403)
        self.assertEqual(
            self.client.get(
                reverse("notice_faq_edit", args=[self.active_faq.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("notice_faq_delete", args=[self.active_faq.pk])
            ).status_code,
            403,
        )

    def test_staff_non_superuser_cannot_manage_faq(self):
        self.client.force_login(self.staff_user)
        list_r = self.client.get(reverse("notice_faq"))
        self.assertEqual(list_r.status_code, 200)
        self.assertFalse(list_r.context["can_manage_faq"])
        self.assertNotContains(list_r, "숨겨진 질문")
        self.assertEqual(self.client.get(reverse("notice_faq_create")).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("notice_faq_edit", args=[self.active_faq.pk]),
                {
                    "question": "스태프 수정",
                    "answer": "불가",
                    "sort_order": 1,
                    "is_active": "on",
                },
            ).status_code,
            403,
        )
