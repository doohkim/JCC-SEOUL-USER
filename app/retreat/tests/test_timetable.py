"""수련회 타임테이블 페이지·API 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from retreat.models import (
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatTimetableEntry,
)
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class RetreatTimetableTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="t_seoul_youth_tt", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="2026 수련회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )

        # 회장단 (편집 권한)
        cls.council = User.objects.create_user(username="council_tt", password="x")
        UserDivisionTeam.objects.create(
            user=cls.council, division=cls.div, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

        # 부서 회장 직급만 — 수련회 회장단 아님.
        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president", defaults={"name": "회장", "level": 80, "sort_order": 20}
        )
        cls.staff = User.objects.create_user(username="staff_tt", password="x")
        cls.staff.role_level = cls.rl_president
        cls.staff.save()
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.div, is_primary=True
        )

        cls.list_url = reverse("api_retreat_event_timetable", args=[cls.event.id])

    def setUp(self):
        self.client = APIClient()

    def _payload(self, **over):
        data = {
            "day": "2026-07-01",
            "start_time": "09:00",
            "end_time": "10:00",
            "title": "개회 예배",
            "location": "본당",
            "description": "",
        }
        data.update(over)
        return data

    def test_page_renders_for_council(self):
        self.client.force_login(self.council)
        r = self.client.get(reverse("retreat_timetable", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "타임테이블")

    def test_council_can_create_entry(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(self.list_url, self._payload(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(
            RetreatTimetableEntry.objects.filter(
                event=self.event, title="개회 예배"
            ).exists()
        )

    def test_org_president_without_council_cannot_access_timetable(self):
        """부서 회장 직급만으로는 타임테이블 API 접근 불가."""
        RetreatTimetableEntry.objects.create(
            event=self.event,
            day=date(2026, 7, 1),
            start_time="09:00",
            title="개회 예배",
        )
        self.client.force_authenticate(self.staff)
        r = self.client.get(self.list_url)
        self.assertEqual(r.status_code, 403)

        r2 = self.client.post(self.list_url, self._payload(title="몰래추가"), format="json")
        self.assertEqual(r2.status_code, 403)

    def test_end_before_start_rejected(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(
            self.list_url,
            self._payload(
                day="2026-07-01",
                start_time="10:00",
                end_day="2026-07-01",
                end_time="09:00",
            ),
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_overnight_end_across_midnight(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(
            self.list_url,
            self._payload(
                day="2026-07-01",
                start_time="23:00",
                end_day="2026-07-02",
                end_time="00:00",
                title="야간 기도",
            ),
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        entry = RetreatTimetableEntry.objects.get(title="야간 기도")
        self.assertEqual(str(entry.day), "2026-07-01")
        self.assertEqual(str(entry.end_day), "2026-07-02")
        self.assertEqual(entry.end_time.strftime("%H:%M"), "00:00")

    def test_overnight_inferred_when_end_day_omitted(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(
            self.list_url,
            self._payload(
                day="2026-07-01",
                start_time="23:00",
                end_time="00:00",
                title="자정 넘김 추론",
            ),
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        entry = RetreatTimetableEntry.objects.get(title="자정 넘김 추론")
        self.assertEqual(str(entry.end_day), "2026-07-02")

    def test_same_day_end_after_start_ok(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(
            self.list_url,
            self._payload(start_time="09:00", end_time="10:00"),
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        entry = RetreatTimetableEntry.objects.get(title="개회 예배")
        self.assertIsNone(entry.end_day)

    def test_council_can_delete_entry(self):
        entry = RetreatTimetableEntry.objects.create(
            event=self.event,
            day=date(2026, 7, 1),
            start_time="09:00",
            title="삭제대상",
        )
        url = reverse(
            "api_retreat_event_timetable_detail", args=[self.event.id, entry.id]
        )
        self.client.force_authenticate(self.council)
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 204, r.content)
        self.assertFalse(RetreatTimetableEntry.objects.filter(pk=entry.id).exists())
