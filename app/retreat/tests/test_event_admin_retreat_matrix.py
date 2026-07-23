"""집회 전체 관리자(event_admin) 권한 매트릭스 — API·페이지 통합 테스트."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
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
    RetreatPickup,
    RetreatTimetableEntry,
)
from retreat.services.staff_capabilities import AccessLevel, effective_capabilities
from users.mixins import ensure_user_profile
from users.models import Division, Region, UserDivisionTeam

User = get_user_model()


def _tt(hour: int, minute: int = 0):
    return timezone.make_aware(datetime(2026, 8, 1, hour, minute))


class _EventAdminMatrixFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.incheon = Region.objects.get(code="incheon")
        cls.div_seoul = Division.objects.create(
            region=cls.seoul, code="ea_seoul_y", name="서울청년"
        )
        cls.div_incheon = Division.objects.create(
            region=cls.incheon, code="ea_ic_y", name="인천청년"
        )

        cls.event = RetreatEvent.objects.create(
            name="2026년 청년부 수련회",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.event_hs = RetreatEvent.objects.create(
            name="2026년 중고등부 수련회",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
        )
        cls.inactive_event = RetreatEvent.objects.create(
            name="비활성 집회",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
            is_active=False,
        )

        cls.group_seoul = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_seoul,
            name="서울1조",
        )
        cls.group_incheon = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.incheon,
            division=cls.div_incheon,
            name="인천1조",
        )

        cls.event_admin = User.objects.create_user(username="ea_matrix", password="x")
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.event_admin,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

        cls.link_user = User.objects.create_user(
            username="ea_link_target", password="x"
        )
        link_profile = ensure_user_profile(cls.link_user)
        link_profile.real_name = "연동실명"
        link_profile.phone = "010-1111-2222"
        link_profile.gender = "female"
        link_profile.save(update_fields=["real_name", "phone", "gender", "updated_at"])
        cls.leader_candidate = User.objects.create_user(
            username="ea_leader_pick", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.leader_candidate, division=cls.div_seoul, is_primary=True
        )

        cls.pending = RetreatAttendee.objects.create(
            group=cls.group_seoul, name="입실전"
        )
        cls.checked_in = RetreatAttendee.objects.create(
            group=cls.group_seoul,
            name="입실중",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.checked_out = RetreatAttendee.objects.create(
            group=cls.group_incheon,
            name="퇴실자",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )

        cls.lodging = Lodging.objects.create(event=cls.event, name="본관")
        cls.room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="101",
            capacity=4,
            region=cls.seoul,
            division=cls.div_seoul,
        )

        cls.arrival_pickup = RetreatPickup.objects.create(
            event=cls.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=cls.group_seoul,
            name="입실전",
            region=cls.seoul,
            division=cls.div_seoul,
            train_time=_tt(10),
            boarding_place="서울역",
            contact="010-1111-2222",
        )

        cls.council_observer = RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=User.objects.create_user(username="ea_obs_del", password="x"),
            role=RetreatCouncilMembership.Role.EVENT_OBSERVER,
        )

        cls.timetable_entry = RetreatTimetableEntry.objects.create(
            event=cls.event,
            day=date(2026, 8, 1),
            start_time="09:00",
            title="개회",
        )

    def setUp(self):
        self.api = APIClient()
        self.page = Client()
        self.api.force_authenticate(self.event_admin)
        self.page.force_login(self.event_admin)


class EventAdminDropdownTests(_EventAdminMatrixFixture):
    """집회 드롭다운 — 활성 집회 전체."""

    def test_event_admin_sees_all_active_events_in_picker(self):
        r = self.page.get(reverse("retreat_dashboard", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        available_ids = {ev.id for ev in r.context["available_events"]}
        self.assertIn(self.event.id, available_ids)
        self.assertIn(self.event_hs.id, available_ids)
        self.assertNotIn(self.inactive_event.id, available_ids)
        self.assertContains(r, 'id="retreatEventPicker"')
        self.assertContains(r, reverse("retreat_dashboard", args=[self.event.id]))
        self.assertContains(r, reverse("retreat_staff_apply", args=[self.event_hs.id]))
        self.assertNotContains(r, reverse("retreat_dashboard", args=[self.event_hs.id]))

    def test_unassigned_event_dashboard_forbidden(self):
        r = self.page.get(reverse("retreat_dashboard", args=[self.event_hs.id]))
        self.assertEqual(r.status_code, 403)


class EventAdminLeaderOnlyDropdownTests(TestCase):
    """조장만 배정된 집회도 드롭다운에 포함."""

    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="ea_hs_only", name="중고등부"
        )
        cls.event_hs = RetreatEvent.objects.create(
            name="2026년 중고등부 수련회",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event_hs,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.leader = User.objects.create_user(username="ea_hs_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

    def test_leader_sees_all_active_events_in_picker(self):
        other = RetreatEvent.objects.create(
            name="다른 활성 집회",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 3),
        )
        client = Client()
        client.force_login(self.leader)
        r = client.get(reverse("retreat_dashboard", args=[self.event_hs.id]))
        self.assertEqual(r.status_code, 200)
        available_ids = {ev.id for ev in r.context["available_events"]}
        self.assertIn(self.event_hs.id, available_ids)
        self.assertIn(other.id, available_ids)
        self.assertContains(r, reverse("retreat_staff_apply", args=[other.id]))


class EventAdminTabPageTests(_EventAdminMatrixFixture):
    def _assert_all_tabs_visible(self, ctx):
        for key in (
            "can_show_dashboard_tab",
            "can_show_groups_tab",
            "can_show_pickup_tab",
            "can_show_lodging_tab",
            "can_show_admin_tab",
        ):
            self.assertTrue(ctx[key], key)

    def test_all_main_pages_return_200(self):
        pages = [
            "retreat_dashboard",
            "retreat_group_manage_list",
            "retreat_pickup",
            "retreat_lodging",
            "retreat_admin",
            "retreat_council",
            "retreat_timetable",
        ]
        for name in pages:
            with self.subTest(page=name):
                r = self.page.get(reverse(name, args=[self.event.id]))
                self.assertEqual(r.status_code, 200, r.content[:200])
                self._assert_all_tabs_visible(r.context)

    def test_manage_group_detail_context_and_clear_button(self):
        r = self.page.get(
            reverse(
                "retreat_group_manage",
                args=[self.event.id, self.group_seoul.id],
            )
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_add_attendee"])
        self.assertTrue(r.context["can_link_attendee_user"])
        self.assertTrue(r.context["can_change_status"])
        self.assertContains(r, "data-user-link-unlink")


class EventAdminDashboardApiTests(_EventAdminMatrixFixture):
    def test_dashboard_includes_all_groups(self):
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.api.get(url).json()
        group_ids = {row["group_id"] for row in data["by_group"]}
        self.assertEqual(group_ids, {self.group_seoul.id, self.group_incheon.id})

    def test_group_board_includes_all_groups(self):
        url = reverse("api_retreat_event_group_board", args=[self.event.id])
        data = self.api.get(url).json()
        names = {g["name"] for g in data["groups"]}
        self.assertIn("서울1조", names)
        self.assertIn("인천1조", names)


class EventAdminGroupApiPageTests(_EventAdminMatrixFixture):
    def test_list_and_create_groups(self):
        list_url = reverse("api_retreat_event_groups", args=[self.event.id])
        r = self.api.post(
            list_url,
            {
                "name": "신규조",
                "region": self.seoul.id,
                "division": self.div_seoul.id,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)

    def test_patch_group_detail(self):
        url = reverse("api_retreat_group_detail", args=[self.group_seoul.id])
        r = self.api.patch(url, {"name": "서울1조-수정"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.group_seoul.refresh_from_db()
        self.assertEqual(self.group_seoul.name, "서울1조-수정")

    def test_manage_list_shows_add_group(self):
        r = self.page.get(reverse("retreat_group_manage_list", args=[self.event.id]))
        self.assertTrue(r.context["can_add_group"])
        self.assertContains(r, "조 추가")

    def test_add_group_leader_membership(self):
        url = reverse("api_retreat_group_memberships", args=[self.group_seoul.id])
        r = self.api.post(
            url,
            {"user_id": self.leader_candidate.id, "role": "leader"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)


class EventAdminAttendeeApiPageTests(_EventAdminMatrixFixture):
    def test_create_and_patch_attendee_fields(self):
        url = reverse("api_retreat_group_attendees", args=[self.group_seoul.id])
        r = self.api.post(url, {"name": "신규조원"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        attendee_id = r.data["id"]

        detail = reverse("api_retreat_attendee_detail", args=[attendee_id])
        future_out = (timezone.now() + timedelta(days=2)).isoformat()
        r2 = self.api.patch(
            detail,
            {
                "name": "이름변경",
                "gender": "female",
                "phone": "01012345678",
                "participation_status": "absent",
                "check_in_status": "checked_in",
                "expected_check_out_at": future_out,
                "note": "메모",
                "user": self.link_user.id,
            },
            format="json",
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        attendee = RetreatAttendee.objects.get(pk=attendee_id)
        self.assertEqual(attendee.name, "연동실명")
        self.assertEqual(attendee.phone, "010-1111-2222")
        self.assertEqual(attendee.gender, "female")
        self.assertEqual(attendee.participation_status, "absent")
        self.assertEqual(attendee.user_id, self.link_user.id)

    def test_link_user_overwrites_manual_name(self):
        attendee = RetreatAttendee.objects.create(
            group=self.group_seoul, name="수동입력"
        )
        detail = reverse("api_retreat_attendee_detail", args=[attendee.id])
        r = self.api.patch(
            detail,
            {"name": "이름변경", "user": self.link_user.id},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        attendee.refresh_from_db()
        self.assertEqual(attendee.name, "연동실명")
        self.assertEqual(attendee.user_id, self.link_user.id)

    def test_unlink_attendee_user(self):
        self.pending.user = self.link_user
        self.pending.save(update_fields=["user"])
        detail = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        r = self.api.patch(detail, {"user": None}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.pending.refresh_from_db()
        self.assertIsNone(self.pending.user_id)

    def test_checked_out_can_revert_to_checked_in(self):
        now = timezone.now()
        self.checked_out.expected_check_out_at = now + timedelta(hours=2)
        self.checked_out.save(update_fields=["expected_check_out_at"])
        detail = reverse("api_retreat_attendee_detail", args=[self.checked_out.id])
        r = self.api.patch(
            detail,
            {
                "check_in_status": "checked_in",
                "expected_check_out_at": (now + timedelta(hours=4)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)

    def test_cannot_delete_checked_out_attendee(self):
        detail = reverse("api_retreat_attendee_detail", args=[self.checked_out.id])
        self.assertEqual(self.api.delete(detail).status_code, 403)


class EventAdminPickupApiPageTests(_EventAdminMatrixFixture):
    def test_pickup_overview_tab_shows_add_button(self):
        r = self.page.get(reverse("retreat_pickup", args=[self.event.id]) + "?tab=all")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_pickup"])
        self.assertContains(r, "btnPickupAdd")
        self.assertContains(r, "jcc-retreat-pickupManageCol")

    def test_arrival_rejects_checked_in_name(self):
        url = reverse("api_retreat_event_pickups", args=[self.event.id])
        r = self.api.post(
            url,
            {
                "direction": "arrival",
                "name": "입실중",
                "group": self.group_seoul.id,
                "train_time": "2026-08-01T12:00",
                "boarding_place": "역",
                "contact": "010-9999-0000",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_departure_pending_and_checked_in_ok(self):
        url = reverse("api_retreat_event_pickups", args=[self.event.id])
        r = self.api.post(
            url,
            {
                "direction": "departure",
                "name": "입실전",
                "group": self.group_seoul.id,
                "train_time": "2026-08-01T19:00",
                "boarding_place": "역",
                "contact": "010-1212-3434",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)

        RetreatAttendee.objects.create(
            group=self.group_seoul,
            name="출회신규",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        r2 = self.api.post(
            url,
            {
                "direction": "departure",
                "name": "출회신규",
                "group": self.group_seoul.id,
                "train_time": "2026-08-01T19:00",
                "boarding_place": "역",
                "contact": "010-5656-7878",
            },
            format="json",
        )
        self.assertEqual(r2.status_code, 201, r2.content)

    def test_pickup_patch(self):
        detail = reverse("api_retreat_pickup_detail", args=[self.arrival_pickup.id])
        r = self.api.patch(detail, {"boarding_place": "수정역"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)


class EventAdminLodgingApiPageTests(_EventAdminMatrixFixture):
    def test_lodging_roster_editable(self):
        r = self.page.get(reverse("retreat_lodging_roster", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["roster_any_can_edit"])


class EventAdminAdminApiPageTests(_EventAdminMatrixFixture):
    def test_council_page_and_group_leader_section(self):
        r = self.page.get(reverse("retreat_council", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_staff"])
        self.assertContains(r, "운영진 관리")
        self.assertContains(r, "staffRosterTbody")
        self.assertContains(r, "btnStaffAddCouncil")
        self.assertContains(r, "staffModalOverlay")

    def test_council_crud(self):
        list_url = reverse("api_retreat_event_council", args=[self.event.id])
        extra = User.objects.create_user(username="ea_new_obs", password="x")
        r = self.api.post(
            list_url,
            {"username": extra.username, "role": "event_observer"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)

    def test_timetable_crud(self):
        list_url = reverse("api_retreat_event_timetable", args=[self.event.id])
        r = self.api.post(
            list_url,
            {
                "day": "2026-08-02",
                "start_time": "14:00",
                "end_time": "15:00",
                "title": "집회예배",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)

    def test_changelog_api(self):
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        self.assertEqual(self.api.get(url).status_code, 200)


class EventAdminCapabilitiesUnitTest(_EventAdminMatrixFixture):
    def test_effective_capabilities(self):
        caps = effective_capabilities(self.event_admin, self.event)
        self.assertTrue(caps.add_group)
        self.assertTrue(caps.link_attendee_user)
        self.assertTrue(caps.delete_attendee)
        self.assertFalse(caps.delete_checked_out_attendee)
        self.assertEqual(caps.pickup_overview, AccessLevel.MUTATE)
        self.assertEqual(caps.pickup_arrival, AccessLevel.MUTATE)
        self.assertEqual(caps.admin, AccessLevel.MUTATE)
