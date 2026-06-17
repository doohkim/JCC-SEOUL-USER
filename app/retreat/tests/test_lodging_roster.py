"""숙소 탭 전체 명단 페이지 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
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
)
from retreat.services.lodging_roster import (
    attendee_lodging_assignment_key,
    attendee_lodging_cell_label,
    attendee_lodging_eligible_key,
    attendee_lodging_scope,
    build_lodging_roster_context,
    is_lodging_eligible,
)
from retreat.services.lodging_stats import build_lodging_page_summary
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


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
            role=RetreatCouncilMembership.Role.CHAIRPERSON,
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
        )
        cls.full_room_attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="만실방",
            expected_check_in_at=timezone.now(),
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
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
            lodging_room=cls.room,
        )


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
        self.assertContains(r, "숙소·호수 관리")
        self.assertContains(r, "미배정자")
        self.assertContains(r, "배정자")
        self.assertContains(r, 'data-lodging-eligible="eligible"')
        self.assertContains(r, 'data-lodging-assignment="unassigned"')
        self.assertContains(r, 'data-lodging-assignment="assigned"')
        self.assertContains(r, 'data-lodging-eligible="ineligible"')
        self.assertContains(r, "숙박 없음")
        self.assertContains(r, "숙박 종료")
        self.assertContains(r, "숙박 여부")
        self.assertContains(r, "호실 배정")
        self.assertContains(r, "숙박 비대상")

    def test_leader_blocked(self):
        self.client.force_login(self.leader)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)

    def test_unassigned_deep_link_query(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url() + "?assign=unassigned")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-filter-value="unassigned"')
        self.assertContains(r, 'data-lodging-assignment="unassigned"')

    def test_legacy_lodging_unassigned_query(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url() + "?lodging=unassigned")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-filter-value="unassigned"')


class LodgingRosterSummaryTests(_LodgingRosterFixture):
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
        self.assertEqual(attendee_lodging_cell_label(by_name["당일참석"]), "숙박 없음")
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
