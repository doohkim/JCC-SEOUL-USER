"""입·퇴실 차량 프리셋 — 부서 필터·조 상세 컨텍스트·시드."""

from __future__ import annotations

from datetime import date, datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatTravelPreset,
)
from retreat.services.travel_presets import (
    travel_bucket_key,
    travel_fixed_and_occurs_map,
    travel_presets_for_group,
)
from users.models import Division, Region, UserDivisionTeam

User = get_user_model()


class TravelPresetServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.youth = Division.objects.create(
            region=cls.seoul, code="tp_youth", name="청년부"
        )
        cls.univ = Division.objects.create(
            region=cls.seoul, code="tp_university", name="대학부"
        )
        cls.kids = Division.objects.create(
            region=cls.seoul, code="tp_kids", name="중고등부"
        )
        cls.event = RetreatEvent.objects.create(
            name="프리셋 테스트 집회",
            start_date=date(2026, 7, 29),
            end_date=date(2026, 8, 1),
        )
        cls.group_youth = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.youth,
            name="청년1조",
        )
        cls.group_kids = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.kids,
            name="중고등1조",
        )
        tz = timezone.get_current_timezone()
        cls.arrival = RetreatTravelPreset.objects.create(
            event=cls.event,
            direction=RetreatTravelPreset.Direction.ARRIVAL,
            code="main",
            label="7/30 본진",
            occurs_at=timezone.make_aware(datetime(2026, 7, 30, 10, 0), tz),
            sort_order=10,
        )
        cls.arrival.divisions.set([cls.youth, cls.univ])
        cls.departure = RetreatTravelPreset.objects.create(
            event=cls.event,
            direction=RetreatTravelPreset.Direction.DEPARTURE,
            code="bus_801",
            label="8/1 버스",
            occurs_at=timezone.make_aware(datetime(2026, 8, 1, 13, 0), tz),
            sort_order=10,
        )
        cls.departure.divisions.set([cls.youth, cls.univ])

    def test_youth_group_gets_arrival_and_departure(self):
        data = travel_presets_for_group(self.group_youth)
        self.assertEqual([p["label"] for p in data["arrival"]], ["7/30 본진"])
        self.assertEqual([p["label"] for p in data["departure"]], ["8/1 버스"])
        self.assertEqual(data["arrival"][0]["occurs_at"], "2026-07-30T10:00")
        self.assertEqual(data["departure"][0]["occurs_at"], "2026-08-01T13:00")
        self.assertFalse(data["arrival"][0]["manual"])

    def test_travel_bucket_key_respects_is_custom(self):
        """자차 명시 시 웨이브와 동일 시각이어도 __custom__."""
        _fixed, occurs = travel_fixed_and_occurs_map([self.arrival])
        wave_at = self.arrival.occurs_at
        self.assertEqual(travel_bucket_key(wave_at, occurs), self.arrival.id)
        self.assertEqual(
            travel_bucket_key(wave_at, occurs, is_custom=None), self.arrival.id
        )
        self.assertEqual(
            travel_bucket_key(wave_at, occurs, is_custom=False), self.arrival.id
        )
        self.assertEqual(
            travel_bucket_key(wave_at, occurs, is_custom=True), "__custom__"
        )
        self.assertEqual(travel_bucket_key(None, occurs), "__unset__")
        self.assertEqual(travel_bucket_key(None, occurs, is_custom=True), "__unset__")

    def test_own_car_is_manual(self):
        tz = timezone.get_current_timezone()
        own = RetreatTravelPreset.objects.create(
            event=self.event,
            direction=RetreatTravelPreset.Direction.ARRIVAL,
            code="own_car_test",
            label="자차",
            occurs_at=None,
            sort_order=1,
        )
        own.divisions.set([self.youth])
        data = travel_presets_for_group(self.group_youth)
        labels = {p["label"]: p for p in data["arrival"]}
        self.assertTrue(labels["자차"]["manual"])
        self.assertEqual(labels["자차"]["occurs_at"], "")

    def test_kids_group_gets_empty_presets(self):
        data = travel_presets_for_group(self.group_kids)
        self.assertEqual(data["arrival"], [])
        self.assertEqual(data["departure"], [])

    def test_inactive_preset_excluded(self):
        self.arrival.is_active = False
        self.arrival.save(update_fields=["is_active"])
        data = travel_presets_for_group(self.group_youth)
        self.assertEqual(data["arrival"], [])
        self.assertEqual(len(data["departure"]), 1)


class TravelPresetManagePageTests(TestCase):
    """템플릿 static manifest 이슈를 피하기 위해 view context만 검증."""

    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.youth = Division.objects.create(
            region=cls.seoul, code="tp_pg_youth", name="청년부"
        )
        cls.kids = Division.objects.create(
            region=cls.seoul, code="tp_pg_kids", name="중고등부"
        )
        cls.event = RetreatEvent.objects.create(
            name="프리셋 페이지 집회",
            start_date=date(2026, 7, 29),
            end_date=date(2026, 8, 1),
        )
        cls.group_youth = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.youth,
            name="청년1조",
        )
        cls.group_kids = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.kids,
            name="중고등1조",
        )
        tz = timezone.get_current_timezone()
        arrival = RetreatTravelPreset.objects.create(
            event=cls.event,
            direction=RetreatTravelPreset.Direction.ARRIVAL,
            code="main",
            label="7/30 본진",
            occurs_at=timezone.make_aware(datetime(2026, 7, 30, 10, 0), tz),
            sort_order=10,
        )
        arrival.divisions.set([cls.youth])
        departure = RetreatTravelPreset.objects.create(
            event=cls.event,
            direction=RetreatTravelPreset.Direction.DEPARTURE,
            code="bus_801",
            label="8/1 버스",
            occurs_at=timezone.make_aware(datetime(2026, 8, 1, 13, 0), tz),
            sort_order=10,
        )
        departure.divisions.set([cls.youth])

        cls.leader = User.objects.create_user(username="tp_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.youth, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group_youth)

        cls.kids_leader = User.objects.create_user(
            username="tp_kids_leader", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.kids_leader, division=cls.kids, is_primary=True
        )
        RetreatGroupMembership.objects.create(
            user=cls.kids_leader, group=cls.group_kids
        )

        cls.admin = User.objects.create_user(username="tp_admin", password="x")
        UserDivisionTeam.objects.create(
            user=cls.admin, division=cls.youth, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.admin,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

        cls.attendee = RetreatAttendee.objects.create(
            group=cls.group_youth,
            name="테스트조원",
            gender=RetreatAttendee.Gender.MALE,
        )

    def setUp(self):
        self.api = APIClient()
        self.factory = RequestFactory()

    def _manage_context(self, user, group):
        from retreat.views import RetreatGroupManageView

        request = self.factory.get(
            reverse(
                "retreat_group_manage",
                args=[self.event.id, group.id],
            )
        )
        request.user = user
        view = RetreatGroupManageView()
        view.setup(request, event_id=self.event.id, group_id=group.id)
        view.request = request
        view.kwargs = {"event_id": self.event.id, "group_id": group.id}
        return view.get_context_data(event_id=self.event.id, group_id=group.id)

    def test_youth_manage_page_includes_presets_in_context(self):
        ctx = self._manage_context(self.leader, self.group_youth)
        presets = ctx["travel_presets"]
        self.assertEqual(presets["arrival"][0]["label"], "7/30 본진")
        self.assertEqual(presets["departure"][0]["label"], "8/1 버스")
        self.assertIn("7/30 본진", ctx["travel_presets_json"])
        self.assertTrue(ctx["can_edit_attendee"])

    def test_kids_manage_page_has_empty_presets(self):
        ctx = self._manage_context(self.kids_leader, self.group_kids)
        self.assertEqual(ctx["travel_presets"]["arrival"], [])
        self.assertEqual(ctx["travel_presets"]["departure"], [])

    def test_leader_can_patch_expected_check_in_datetime(self):
        """프리셋 선택 결과는 datetime PATCH — 조장도 기존 권한으로 저장."""
        self.api.force_authenticate(user=self.leader)
        url = reverse("api_retreat_attendee_detail", args=[self.attendee.id])
        r = self.api.patch(
            url,
            {"expected_check_in_at": "2026-07-30T10:00:00+09:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.attendee.refresh_from_db()
        local = timezone.localtime(self.attendee.expected_check_in_at)
        self.assertEqual(local.strftime("%Y-%m-%d %H:%M"), "2026-07-30 10:00")

    def test_patch_arrival_travel_is_custom_round_trip_and_clear(self):
        self.api.force_authenticate(user=self.leader)
        url = reverse("api_retreat_attendee_detail", args=[self.attendee.id])
        r = self.api.patch(
            url,
            {
                "expected_check_in_at": "2026-07-30T10:00:00+09:00",
                "arrival_travel_is_custom": True,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data["arrival_travel_is_custom"])
        self.attendee.refresh_from_db()
        self.assertTrue(self.attendee.arrival_travel_is_custom)

        r2 = self.api.patch(
            url,
            {"expected_check_in_at": None},
            format="json",
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        self.attendee.refresh_from_db()
        self.assertIsNone(self.attendee.expected_check_in_at)
        self.assertIsNone(self.attendee.arrival_travel_is_custom)

    def test_event_admin_gets_same_division_presets(self):
        ctx = self._manage_context(self.admin, self.group_youth)
        self.assertEqual(ctx["travel_presets"]["arrival"][0]["label"], "7/30 본진")
        self.assertNotEqual(
            [p["label"] for p in ctx["travel_presets"]["arrival"]],
            [p["label"] for p in ctx["travel_presets"]["departure"]],
        )


class SeedTravelPresetsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        # 시드 커맨드가 찾는 표준 코드
        cls.youth = Division.objects.create(
            region=cls.seoul, code="youth", name="청년부"
        )
        cls.univ = Division.objects.create(
            region=cls.seoul, code="university", name="대학부"
        )
        cls.event = RetreatEvent.objects.create(
            name="시드 집회",
            start_date=date(2026, 7, 29),
            end_date=date(2026, 8, 1),
        )

    def test_seed_creates_youth_university_presets(self):
        out = StringIO()
        call_command(
            "seed_travel_presets",
            event_id=self.event.id,
            stdout=out,
        )
        qs = RetreatTravelPreset.objects.filter(event=self.event)
        self.assertGreaterEqual(qs.filter(direction="arrival").count(), 4)
        self.assertGreaterEqual(qs.filter(direction="departure").count(), 4)
        main = qs.get(direction="arrival", code="main")
        self.assertEqual(main.label, "7/30 본진")
        self.assertEqual(
            set(main.divisions.values_list("code", flat=True)),
            {"youth", "university"},
        )
