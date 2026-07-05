"""superuser 수련회 권한 매트릭스 — API·페이지 통합 테스트."""

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


class _SuperuserMatrixFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.incheon = Region.objects.get(code="incheon")
        cls.div_seoul = Division.objects.create(
            region=cls.seoul, code="su_seoul_y", name="서울청년"
        )
        cls.div_incheon = Division.objects.create(
            region=cls.incheon, code="su_ic_y", name="인천청년"
        )

        cls.event = RetreatEvent.objects.create(
            name="슈퍼유저 매트릭스 A",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.event2 = RetreatEvent.objects.create(
            name="슈퍼유저 매트릭스 B",
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

        cls.superuser = User.objects.create_superuser(
            username="su_matrix", password="x"
        )
        cls.link_user = User.objects.create_user(username="su_link_target", password="x")
        link_profile = ensure_user_profile(cls.link_user)
        link_profile.real_name = "연동실명"
        link_profile.phone = "010-1111-2222"
        link_profile.gender = "female"
        link_profile.save(update_fields=["real_name", "phone", "gender", "updated_at"])
        cls.leader_candidate = User.objects.create_user(
            username="su_leader_pick", password="x"
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
        cls.departure_pickup = RetreatPickup.objects.create(
            event=cls.event,
            direction=RetreatPickup.Direction.DEPARTURE,
            number=1,
            group=cls.group_seoul,
            name="입실중",
            region=cls.seoul,
            division=cls.div_seoul,
            train_time=_tt(18),
            boarding_place="서울역",
            contact="010-3333-4444",
        )

        cls.council_member = RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=User.objects.create_user(username="su_council_del", password="x"),
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
        self.api.force_authenticate(self.superuser)
        self.page.force_login(self.superuser)


class SuperuserTabPageTests(_SuperuserMatrixFixture):
    """1.1 집회 선택·탭 접근."""

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

    def test_event_picker_lists_active_events(self):
        r = self.page.get(reverse("retreat_dashboard", args=[self.event.id]))
        available_ids = {ev.id for ev in r.context["available_events"]}
        self.assertIn(self.event.id, available_ids)
        self.assertIn(self.event2.id, available_ids)
        self.assertNotIn(self.inactive_event.id, available_ids)
        self.assertContains(r, 'id="retreatEventPicker"')

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
        self.assertContains(r, 'id="retreatAttCheckIn"')
        self.assertContains(r, 'data-user-link-unlink')


class SuperuserDashboardApiTests(_SuperuserMatrixFixture):
    """1.2 대시보드 API."""

    def test_dashboard_includes_all_groups(self):
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.api.get(url).json()
        group_ids = {row["group_id"] for row in data["by_group"]}
        self.assertEqual(
            group_ids, {self.group_seoul.id, self.group_incheon.id}
        )

    def test_group_board_includes_all_groups(self):
        url = reverse("api_retreat_event_group_board", args=[self.event.id])
        data = self.api.get(url).json()
        names = {g["name"] for g in data["groups"]}
        self.assertIn("서울1조", names)
        self.assertIn("인천1조", names)


class SuperuserGroupApiPageTests(_SuperuserMatrixFixture):
    """1.3 그룹 API·페이지."""

    def test_list_and_create_groups(self):
        list_url = reverse("api_retreat_event_groups", args=[self.event.id])
        data = self.api.get(list_url).json()
        names = {g["name"] for g in data}
        self.assertIn("서울1조", names)
        self.assertIn("인천1조", names)

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
        r = self.page.get(
            reverse("retreat_group_manage_list", args=[self.event.id])
        )
        self.assertEqual(r.status_code, 200)
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
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=self.group_seoul, user=self.leader_candidate
            ).exists()
        )

    def test_user_search_respects_division_filter(self):
        url = reverse("api_retreat_user_search")
        r = self.api.get(url, {"division": self.div_seoul.id, "q": "su_leader"})
        self.assertEqual(r.status_code, 200)
        usernames = {row["username"] for row in r.json()}
        self.assertIn(self.leader_candidate.username, usernames)


class SuperuserAttendeeApiPageTests(_SuperuserMatrixFixture):
    """1.4 조원 상세 API·페이지."""

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

        participating = RetreatAttendee.objects.create(
            group=self.group_seoul, name="숙소배정대상"
        )
        detail2 = reverse("api_retreat_attendee_detail", args=[participating.id])
        r3 = self.api.patch(
            detail2, {"lodging_room": self.room.id}, format="json"
        )
        self.assertEqual(r3.status_code, 200, r3.content)

    def test_unlink_attendee_user(self):
        self.pending.user = self.link_user
        self.pending.save(update_fields=["user"])
        detail = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        r = self.api.patch(detail, {"user": None}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.pending.refresh_from_db()
        self.assertIsNone(self.pending.user_id)

    def test_unlink_leader_removes_group_membership(self):
        from retreat.services.group_sync import (
            sync_attendee_from_membership,
            sync_membership_from_attendee,
        )
        from users.mixins import ensure_user_profile

        profile = ensure_user_profile(self.link_user)
        profile.real_name = "김실업"
        profile.save(update_fields=["real_name", "updated_at"])
        attendee = RetreatAttendee.objects.create(
            group=self.group_seoul,
            name="김실업",
            gender="female",
            member_role=RetreatAttendee.MemberRole.LEADER,
            user=self.link_user,
        )
        sync_membership_from_attendee(attendee, changed_by=self.superuser)
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=self.group_seoul, user=self.link_user
            ).exists()
        )

        detail = reverse("api_retreat_attendee_detail", args=[attendee.id])
        r = self.api.patch(
            detail,
            {"user": None, "member_role": "leader"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        attendee.refresh_from_db()
        self.assertIsNone(attendee.user_id)
        self.assertEqual(attendee.member_role, RetreatAttendee.MemberRole.MEMBER)
        self.assertFalse(
            RetreatGroupMembership.objects.filter(
                group=self.group_seoul, user=self.link_user
            ).exists()
        )

        # 멤버십이 남아 있어도 동기화가 계정을 다시 붙이지 않아야 한다.
        orphan_membership = RetreatGroupMembership.objects.create(
            group=self.group_seoul,
            user=self.link_user,
            role=RetreatGroupMembership.Role.LEADER,
        )
        sync_attendee_from_membership(orphan_membership, changed_by=self.superuser)
        attendee.refresh_from_db()
        self.assertIsNone(attendee.user_id)

    def test_change_leader_user_updates_group_membership(self):
        from retreat.services.group_sync import sync_membership_from_attendee
        from users.mixins import ensure_user_profile

        other_user = User.objects.create_user(username="su_other_leader", password="x")
        other_profile = ensure_user_profile(other_user)
        other_profile.real_name = "김실업"
        other_profile.gender = other_profile.Gender.FEMALE
        other_profile.phone = "01099998888"
        other_profile.save(
            update_fields=["real_name", "gender", "phone", "updated_at"]
        )
        profile = ensure_user_profile(self.link_user)
        profile.real_name = "김샬롬"
        profile.save(update_fields=["real_name", "updated_at"])

        attendee = RetreatAttendee.objects.create(
            group=self.group_seoul,
            name="김샬롬",
            gender="female",
            member_role=RetreatAttendee.MemberRole.LEADER,
            user=self.link_user,
        )
        sync_membership_from_attendee(attendee, changed_by=self.superuser)

        detail = reverse("api_retreat_attendee_detail", args=[attendee.id])
        r = self.api.patch(
            detail,
            {"user": other_user.id, "member_role": "leader"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        attendee.refresh_from_db()
        self.assertEqual(attendee.user_id, other_user.id)
        self.assertEqual(attendee.name, "김실업")
        self.assertFalse(
            RetreatGroupMembership.objects.filter(
                group=self.group_seoul, user=self.link_user
            ).exists()
        )
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=self.group_seoul,
                user=other_user,
                role=RetreatGroupMembership.Role.LEADER,
            ).exists()
        )

        from retreat.services.group_sync import sync_attendee_from_membership

        orphan_membership = RetreatGroupMembership.objects.create(
            group=self.group_seoul,
            user=self.link_user,
            role=RetreatGroupMembership.Role.LEADER,
        )
        sync_attendee_from_membership(orphan_membership, changed_by=self.superuser)
        attendee.refresh_from_db()
        self.assertEqual(attendee.user_id, other_user.id)

    def test_checked_out_can_revert_to_checked_in(self):
        now = timezone.now()
        self.checked_out.expected_check_out_at = now + timedelta(hours=2)
        self.checked_out.save(update_fields=["expected_check_out_at"])
        detail = reverse("api_retreat_attendee_detail", args=[self.checked_out.id])
        new_out = (now + timedelta(hours=4)).isoformat()
        r = self.api.patch(
            detail,
            {"check_in_status": "checked_in", "expected_check_out_at": new_out},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.checked_out.refresh_from_db()
        self.assertEqual(
            self.checked_out.check_in_status,
            RetreatAttendee.CheckInStatus.CHECKED_IN,
        )

    def test_delete_checked_out_attendee(self):
        victim = RetreatAttendee.objects.create(
            group=self.group_incheon,
            name="삭제대상",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        detail = reverse("api_retreat_attendee_detail", args=[victim.id])
        self.assertEqual(self.api.delete(detail).status_code, 200)
        self.assertFalse(RetreatAttendee.objects.filter(pk=victim.id).exists())


class SuperuserPickupApiPageTests(_SuperuserMatrixFixture):
    """1.5 픽업 API·페이지."""

    def _pickup_url(self, direction: str):
        return (
            reverse("api_retreat_event_pickups", args=[self.event.id])
            + f"?direction={direction}"
        )

    def test_list_arrival_and_departure_all_groups(self):
        arrival = self.api.get(self._pickup_url("arrival")).json()
        departure = self.api.get(self._pickup_url("departure")).json()
        self.assertGreaterEqual(len(arrival), 1)
        self.assertGreaterEqual(len(departure), 1)

    def test_arrival_pending_ok_checked_in_rejected(self):
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
        self.assertIn("name", r.json())

        RetreatAttendee.objects.create(group=self.group_incheon, name="신규입회")
        r2 = self.api.post(
            url,
            {
                "direction": "arrival",
                "name": "신규입회",
                "group": self.group_incheon.id,
                "train_time": "2026-08-01T11:00",
                "boarding_place": "역",
                "contact": "010-7777-8888",
            },
            format="json",
        )
        self.assertEqual(r2.status_code, 201, r2.content)

    def test_departure_checked_in_ok_pending_rejected(self):
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
        self.assertEqual(r.status_code, 400)

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

    def test_pickup_crud_and_page(self):
        detail = reverse(
            "api_retreat_pickup_detail", args=[self.arrival_pickup.id]
        )
        r = self.api.patch(
            detail, {"boarding_place": "수정역", "note": "비고"}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.content)

        r = self.page.get(
            reverse("retreat_pickup", args=[self.event.id]) + "?tab=arrival"
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_pickup"])
        self.assertTrue(r.context["can_manage_pickup_location"])


class SuperuserLodgingApiPageTests(_SuperuserMatrixFixture):
    """1.6 숙소 API·페이지."""

    def test_lodging_and_room_crud(self):
        list_url = reverse("api_retreat_event_lodgings", args=[self.event.id])
        r = self.api.post(list_url, {"name": "별관"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        lodging_id = r.data["id"]

        detail = reverse("api_retreat_lodging_detail", args=[lodging_id])
        self.assertEqual(
            self.api.patch(detail, {"name": "별관-수정"}, format="json").status_code,
            200,
        )

        rooms_url = reverse("api_retreat_lodging_rooms", args=[lodging_id])
        r2 = self.api.post(
            rooms_url,
            {
                "number": "201",
                "capacity": 2,
                "region": self.seoul.id,
                "division": self.div_seoul.id,
            },
            format="json",
        )
        self.assertEqual(r2.status_code, 201, r2.content)
        room_id = r2.data["id"]

        room_detail = reverse("api_retreat_lodging_room_detail", args=[room_id])
        self.assertEqual(self.api.delete(room_detail).status_code, 204)
        self.assertEqual(self.api.delete(detail).status_code, 204)

    def test_lodging_pages_and_roster_edit(self):
        r = self.page.get(reverse("retreat_lodging", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)

        r2 = self.page.get(
            reverse("retreat_lodging_roster", args=[self.event.id])
        )
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.context["roster_any_can_edit"])

        detail = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        r3 = self.api.patch(
            detail, {"lodging_room": self.room.id}, format="json"
        )
        self.assertEqual(r3.status_code, 200, r3.content)


class SuperuserAdminApiPageTests(_SuperuserMatrixFixture):
    """1.7 관리(운영진·타임테이블·변경이력) API·페이지."""

    def test_council_crud(self):
        list_url = reverse("api_retreat_event_council", args=[self.event.id])
        self.assertEqual(self.api.get(list_url).status_code, 200)

        extra = User.objects.create_user(username="su_new_council", password="x")
        r = self.api.post(
            list_url,
            {"username": extra.username, "role": "event_observer"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        membership_id = r.data["id"]

        detail = reverse(
            "api_retreat_event_council_detail",
            args=[self.event.id, membership_id],
        )
        self.assertEqual(
            self.api.patch(detail, {"note": "비고"}, format="json").status_code,
            200,
        )
        self.assertEqual(self.api.delete(detail).status_code, 204)

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
        entry_id = r.data["id"]

        detail = reverse(
            "api_retreat_event_timetable_detail",
            args=[self.event.id, entry_id],
        )
        self.assertEqual(
            self.api.patch(detail, {"title": "집회예배-수정"}, format="json").status_code,
            200,
        )
        self.assertEqual(self.api.delete(detail).status_code, 204)

    def test_changelog_api(self):
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        self.assertEqual(self.api.get(url).status_code, 200)

    def test_admin_subpages(self):
        r = self.page.get(reverse("retreat_council", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_staff"])
        self.assertContains(r, "운영진 관리")

        r2 = self.page.get(reverse("retreat_timetable", args=[self.event.id]))
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, "일정 추가")

        r3 = self.page.get(
            reverse("retreat_admin", args=[self.event.id]) + "?tab=changelog"
        )
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.context["active_tab"], "changelog")
        self.assertIn("changelog_entries", r3.context)


class SuperuserCapabilitiesUnitTest(_SuperuserMatrixFixture):
    def test_effective_capabilities_match_event_admin_plus_delete(self):
        caps = effective_capabilities(self.superuser, self.event)
        self.assertTrue(caps.add_group)
        self.assertTrue(caps.link_attendee_user)
        self.assertTrue(caps.change_check_in)
        self.assertTrue(caps.delete_checked_out_attendee)
        self.assertEqual(caps.pickup_arrival, AccessLevel.MUTATE)
        self.assertEqual(caps.admin, AccessLevel.MUTATE)
