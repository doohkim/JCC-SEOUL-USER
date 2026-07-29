"""숙소 탭 전체 명단 페이지 테스트."""

from __future__ import annotations

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from retreat.models import (
    Lodging,
    LodgingRoom,
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatGroupScope,
    RetreatTravelPreset,
)
from retreat.services.lodging_roster import (
    attendee_lodging_assignment_key,
    attendee_lodging_cell_label,
    attendee_lodging_eligible_key,
    attendee_lodging_scope,
    build_lodging_roster_context,
    is_lodging_eligible,
    lodging_night_count,
)
from retreat.services.lodging import room_assignment_options_for_groups
from retreat.services.lodging_stats import build_lodging_page_summary
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()

_STATICFILES_STORAGE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


class _LodgingRosterFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="roster_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="명단 집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.leader = User.objects.create_user(username="roster_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.rl_pastor, _ = RoleLevel.objects.get_or_create(
            code="pastor",
            defaults={"name": "목사", "level": 90, "sort_order": 10},
        )
        cls.staff = User.objects.create_user(username="roster_pastor", password="x")
        cls.staff.role_level = cls.rl_pastor
        cls.staff.save()
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.div, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.staff,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

        cls.lodging = Lodging.objects.create(event=cls.event, name="본관")
        cls.room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="101",
            capacity=2,
            region=cls.seoul,
            division=cls.div,
        )
        cls.unassigned_attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="미배정자",
            expected_check_in_at=timezone.now(),
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        cls.assigned_attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="배정자",
            expected_check_in_at=timezone.now(),
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            lodging_room=cls.room,
            memo="알레르기주의필요",
        )
        cls.full_room_attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="만실방",
            expected_check_in_at=timezone.now(),
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            check_in_status_manually_set=True,
            lodging_room=cls.room,
        )
        cls.no_lodging_attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="당일참석",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        cls.checked_out_attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="퇴실자",
            expected_check_in_at=timezone.now(),
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
            check_in_status_manually_set=True,
            lodging_room=cls.room,
        )
        from retreat.services.lodging_stay import persist_lodging_stay_status

        for attendee in (
            cls.unassigned_attendee,
            cls.assigned_attendee,
            cls.full_room_attendee,
            cls.no_lodging_attendee,
            cls.checked_out_attendee,
        ):
            persist_lodging_stay_status(attendee)


@override_settings(STORAGES=_STATICFILES_STORAGE)
class LodgingRosterPageTests(_LodgingRosterFixture):
    def setUp(self):
        self.client = APIClient()

    def _url(self):
        return reverse("retreat_lodging_roster", args=[self.event.id])

    def test_pastor_sees_roster_page(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "전체 명단")
        self.assertContains(r, "조별 관리")
        self.assertContains(r, 'aria-label="그룹 서브탭"')
        self.assertContains(r, "미배정자")
        self.assertContains(r, "배정자")
        self.assertContains(r, 'data-lodging-stay-status="active"')
        self.assertContains(r, 'data-lodging-stay-status="unassigned"')
        self.assertContains(r, 'data-filter-value="ended"')
        self.assertContains(r, "jcc-retreat-lodgingStayBadge--active")
        self.assertContains(r, "jcc-retreat-lodgingStayBadge--unassigned")
        self.assertContains(r, "입실 예정 없음")
        self.assertContains(r, "숙박 종료")
        self.assertContains(r, "숙소 상태")
        self.assertContains(r, 'data-filter-kind="lodgingStay"')
        self.assertContains(r, "숙박 관리 대상")
        self.assertContains(r, 'data-filter-kind="memo"')
        self.assertContains(r, 'data-filter-value="1"')
        self.assertContains(r, "data-roster-memo")
        self.assertContains(r, 'data-memo-full="알레르기주의필요"')
        self.assertContains(r, 'data-filter-kind="gender"')
        self.assertContains(r, 'id="rosterDateFrom"')
        self.assertContains(r, 'data-filter-kind="nights"')
        self.assertContains(r, 'id="rosterFilterRegions"')
        self.assertContains(r, 'id="rosterFilterDivisions"')
        self.assertContains(r, 'data-region-names="서울"')
        self.assertContains(r, 'data-division-names="청년부"')
        self.assertContains(r, "숙박 X")

    def test_extra_group_scope_is_exposed_to_region_division_filters(self):
        adult_division = Division.objects.create(
            region=self.seoul,
            code="roster_young_adult",
            name="청장년부",
        )
        RetreatGroupScope.objects.create(
            group=self.group,
            region=self.seoul,
            division=adult_division,
        )
        self.client.force_login(self.staff)
        response = self.client.get(self._url())
        self.assertContains(response, 'data-region-names="서울"')
        self.assertContains(response, 'data-division-names="청년부|청장년부"')
        self.assertContains(response, "서울 · 청년부, 서울 · 청장년부")

    def test_memo_filter_query_param_page_ok(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url() + "?memo=1")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-filter-kind="memo"')
        self.assertContains(r, "data-roster-memo")

    def test_leader_blocked(self):
        self.client.force_login(self.leader)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)

    def test_unassigned_deep_link_query(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url() + "?assign=unassigned")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-filter-value="unassigned"')
        self.assertContains(r, 'data-lodging-stay-status="unassigned"')

    def test_legacy_lodging_unassigned_query(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url() + "?lodging=unassigned")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-filter-value="unassigned"')

    def test_page_renders_only_first_twenty_attendees(self):
        RetreatAttendee.objects.bulk_create(
            [
                RetreatAttendee(group=self.group, name=f"추가조원{i:02d}")
                for i in range(25)
            ]
        )
        self.client.force_login(self.staff)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.count(b'data-attendee-id="'), 20)
        self.assertContains(
            response,
            reverse("api_retreat_event_lodging_roster", args=[self.event.id]),
        )

    def test_roster_api_paginates_and_returns_filtered_summary(self):
        RetreatAttendee.objects.bulk_create(
            [
                RetreatAttendee(group=self.group, name=f"API조원{i:02d}")
                for i in range(25)
            ]
        )
        self.client.force_login(self.staff)
        url = reverse("api_retreat_event_lodging_roster", args=[self.event.id])
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["page_size"], 20)
        self.assertEqual(first.json()["total"], 30)
        self.assertEqual(first.json()["rows_html"].count('data-attendee-id="'), 20)

        filtered = self.client.get(url, {"lodgingStay": "unassigned"})
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()["total"], 1)
        self.assertEqual(
            filtered.json()["summary"]["count_lodging_unassigned"],
            1,
        )

    def test_roster_api_uses_same_roster_permission(self):
        self.client.force_login(self.leader)
        url = reverse("api_retreat_event_lodging_roster", args=[self.event.id])
        self.assertEqual(self.client.get(url).status_code, 403)


class LodgingRosterSummaryTests(_LodgingRosterFixture):
    def test_room_assignment_options_for_groups_uses_one_room_query(self):
        group = RetreatGroup.objects.prefetch_related("extra_scopes").get(
            pk=self.group.pk
        )
        with self.assertNumQueries(1):
            options = room_assignment_options_for_groups(self.event, [group])
        self.assertEqual([row["id"] for row in options[group.id]], [self.room.id])
        self.assertEqual(options[group.id][0]["assigned_count"], 2)

    def test_lodging_nights_count_only_0200_to_0700_overlap(self):
        attendee = self.assigned_attendee
        attendee.expected_check_in_at = timezone.make_aware(datetime(2026, 7, 1, 23, 0))
        attendee.expected_check_out_at = timezone.make_aware(
            datetime(2026, 7, 3, 2, 30)
        )
        self.assertEqual(lodging_night_count(attendee), 2)

        attendee.expected_check_in_at = timezone.make_aware(datetime(2026, 7, 1, 7, 0))
        attendee.expected_check_out_at = timezone.make_aware(
            datetime(2026, 7, 1, 23, 59)
        )
        self.assertEqual(lodging_night_count(attendee), 0)

    def test_context_exposes_night_filter_chips_and_labels(self):
        self.assigned_attendee.expected_check_in_at = timezone.make_aware(
            datetime(2026, 7, 1, 1, 0)
        )
        self.assigned_attendee.expected_check_out_at = timezone.make_aware(
            datetime(2026, 7, 2, 8, 0)
        )
        self.assigned_attendee.save(
            update_fields=["expected_check_in_at", "expected_check_out_at"]
        )
        ctx = build_lodging_roster_context(self.event, self.staff)
        by_name = {a.name: a for a in ctx["roster_attendees"]}
        self.assertEqual(by_name["배정자"].lodging_nights, 2)
        self.assertEqual(by_name["배정자"].lodging_nights_label, "2박")
        self.assertEqual(
            ctx["roster_night_chips"],
            [
                ("0", "숙박 X"),
                ("1", "1박"),
                ("2", "2박 이상"),
            ],
        )

    def test_summary_matches_lodging_stats_unassigned(self):
        ctx = build_lodging_roster_context(self.event, self.staff)
        facility = build_lodging_page_summary(self.event).facility
        self.assertEqual(
            ctx["roster_summary"].count_lodging_unassigned,
            facility.unassigned_eligible,
        )
        self.assertEqual(ctx["roster_summary"].count_lodging_eligible, 3)
        self.assertEqual(ctx["roster_summary"].count_total, 5)

    def test_lodging_scope_on_attendees(self):
        ctx = build_lodging_roster_context(self.event, self.staff)
        by_name = {a.name: a.lodging_scope for a in ctx["roster_attendees"]}
        self.assertEqual(by_name["미배정자"], "unassigned")
        self.assertEqual(by_name["배정자"], "assigned")
        self.assertEqual(by_name["당일참석"], "na")
        self.assertEqual(by_name["퇴실자"], "na")

    def test_lodging_eligible_and_assignment_keys(self):
        ctx = build_lodging_roster_context(self.event, self.staff)
        by_name = {a.name: a for a in ctx["roster_attendees"]}
        self.assertEqual(by_name["미배정자"].lodging_eligible_key, "eligible")
        self.assertEqual(by_name["미배정자"].lodging_assignment_key, "unassigned")
        self.assertEqual(by_name["배정자"].lodging_assignment_key, "assigned")
        self.assertEqual(by_name["당일참석"].lodging_eligible_key, "ineligible")
        self.assertEqual(by_name["당일참석"].lodging_assignment_key, "")
        self.assertEqual(by_name["퇴실자"].lodging_eligible_key, "ineligible")
        self.assertEqual(
            attendee_lodging_cell_label(by_name["당일참석"]), "입실 예정 없음"
        )
        self.assertEqual(attendee_lodging_cell_label(by_name["퇴실자"]), "숙박 종료")
        self.assertIsNone(attendee_lodging_cell_label(by_name["배정자"]))

    def test_eligible_helpers(self):
        self.assertTrue(is_lodging_eligible(self.unassigned_attendee))
        self.assertFalse(is_lodging_eligible(self.no_lodging_attendee))
        self.assertFalse(is_lodging_eligible(self.checked_out_attendee))
        self.assertEqual(
            attendee_lodging_eligible_key(self.unassigned_attendee), "eligible"
        )
        self.assertEqual(
            attendee_lodging_assignment_key(self.unassigned_attendee), "unassigned"
        )
        self.assertEqual(attendee_lodging_scope(self.checked_out_attendee), "na")


class LodgingRosterTravelFilterTests(_LodgingRosterFixture):
    """템플릿 static manifest 이슈를 피하기 위해 context만 검증."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.arrival_main = RetreatTravelPreset.objects.create(
            event=cls.event,
            direction=RetreatTravelPreset.Direction.ARRIVAL,
            code="main",
            label="7/1 본진",
            occurs_at=timezone.make_aware(datetime(2026, 7, 1, 10, 0)),
            sort_order=10,
        )
        cls.departure_bus = RetreatTravelPreset.objects.create(
            event=cls.event,
            direction=RetreatTravelPreset.Direction.DEPARTURE,
            code="bus",
            label="7/3 버스",
            occurs_at=timezone.make_aware(datetime(2026, 7, 3, 13, 0)),
            sort_order=10,
        )

    def test_travel_chips_and_row_keys(self):
        wave_in = timezone.make_aware(datetime(2026, 7, 1, 10, 0))
        custom_in = timezone.make_aware(datetime(2026, 7, 1, 15, 30))
        wave_out = timezone.make_aware(datetime(2026, 7, 3, 13, 0))

        self.assigned_attendee.expected_check_in_at = wave_in
        self.assigned_attendee.expected_check_out_at = wave_out
        self.assigned_attendee.save(
            update_fields=["expected_check_in_at", "expected_check_out_at"]
        )
        self.unassigned_attendee.expected_check_in_at = custom_in
        self.unassigned_attendee.expected_check_out_at = None
        self.unassigned_attendee.save(
            update_fields=["expected_check_in_at", "expected_check_out_at"]
        )

        ctx = build_lodging_roster_context(self.event, self.staff)
        arrival_values = [c["value"] for c in ctx["roster_arrival_travel_chips"]]
        departure_values = [c["value"] for c in ctx["roster_departure_travel_chips"]]
        self.assertIn(str(self.arrival_main.id), arrival_values)
        self.assertIn("__custom__", arrival_values)
        self.assertIn("__unset__", arrival_values)
        self.assertIn(str(self.departure_bus.id), departure_values)
        self.assertEqual(ctx["roster_arrival_travel_chips"][0]["label"], "7/1 본진")
        self.assertEqual(ctx["roster_departure_travel_chips"][0]["label"], "7/3 버스")

        by_name = {a.name: a for a in ctx["roster_attendees"]}
        self.assertEqual(
            by_name["배정자"].arrival_travel_key, str(self.arrival_main.id)
        )
        self.assertEqual(
            by_name["배정자"].departure_travel_key, str(self.departure_bus.id)
        )
        self.assertEqual(by_name["미배정자"].arrival_travel_key, "__custom__")
        self.assertEqual(by_name["미배정자"].departure_travel_key, "__unset__")
        self.assertEqual(by_name["당일참석"].arrival_travel_key, "__unset__")

    def test_custom_flag_keeps_wave_time_as_own_car(self):
        wave_in = timezone.make_aware(datetime(2026, 7, 1, 10, 0))
        wave_out = timezone.make_aware(datetime(2026, 7, 3, 13, 0))
        self.assigned_attendee.expected_check_in_at = wave_in
        self.assigned_attendee.expected_check_out_at = wave_out
        self.assigned_attendee.arrival_travel_is_custom = True
        self.assigned_attendee.departure_travel_is_custom = True
        self.assigned_attendee.save(
            update_fields=[
                "expected_check_in_at",
                "expected_check_out_at",
                "arrival_travel_is_custom",
                "departure_travel_is_custom",
            ]
        )
        ctx = build_lodging_roster_context(self.event, self.staff)
        by_name = {a.name: a for a in ctx["roster_attendees"]}
        self.assertEqual(by_name["배정자"].arrival_travel_key, "__custom__")
        self.assertEqual(by_name["배정자"].departure_travel_key, "__custom__")

    def test_default_chips_without_presets(self):
        RetreatTravelPreset.objects.filter(event=self.event).delete()
        ctx = build_lodging_roster_context(self.event, self.staff)
        self.assertEqual(
            [c["value"] for c in ctx["roster_arrival_travel_chips"]],
            ["__custom__", "__unset__"],
        )
        self.assertEqual(
            [c["value"] for c in ctx["roster_departure_travel_chips"]],
            ["__custom__", "__unset__"],
        )
