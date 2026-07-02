"""숙소·호실 모델·API·배정 검증 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
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
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class LodgingModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = RetreatEvent.objects.create(
            name="숙소 모델",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )

    def test_lodging_unique_event_name(self):
        Lodging.objects.create(event=self.event, name="본관")
        with self.assertRaises(IntegrityError):
            Lodging.objects.create(event=self.event, name="본관")

    def test_room_unique_lodging_number(self):
        lodging = Lodging.objects.create(event=self.event, name="별관")
        LodgingRoom.objects.create(lodging=lodging, number="101")
        with self.assertRaises(IntegrityError):
            LodgingRoom.objects.create(lodging=lodging, number="101")


class _LodgingFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="lodging_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="숙소 집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.other_event = RetreatEvent.objects.create(
            name="다른 집회",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.other_group = RetreatGroup.objects.create(
            event=cls.other_event,
            region=cls.seoul,
            division=cls.div,
            name="2조",
        )

        cls.leader = User.objects.create_user(username="lodging_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president",
            defaults={"name": "회장", "level": 80, "sort_order": 20},
        )
        cls.staff = User.objects.create_user(username="lodging_staff", password="x")
        cls.staff.role_level = cls.rl_president
        cls.staff.save()
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.div, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.staff,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

        cls.outsider = User.objects.create_user(
            username="lodging_outsider", password="x"
        )


class LodgingApiPermissionTests(_LodgingFixture):
    def setUp(self):
        self.client = APIClient()

    def _url(self):
        return reverse("api_retreat_event_lodgings", args=[self.event.id])

    def test_staff_can_create_lodging(self):
        self.client.force_authenticate(self.staff)
        r = self.client.post(self._url(), {"name": "본관"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Lodging.objects.filter(event=self.event).count(), 1)

    def test_leader_cannot_create_lodging(self):
        self.client.force_authenticate(self.leader)
        r = self.client.post(self._url(), {"name": "본관"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_leader_cannot_list_lodgings(self):
        Lodging.objects.create(event=self.event, name="본관")
        self.client.force_authenticate(self.leader)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)

    def test_outsider_blocked_from_listing(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)


class LodgingRoomAssignmentTests(_LodgingFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.lodging = Lodging.objects.create(event=cls.event, name="본관")
        cls.room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="101",
            capacity=2,
            region=cls.seoul,
            division=cls.div,
        )
        cls.male_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="102",
            capacity=2,
            recommended_gender=LodgingRoom.Gender.MALE,
            region=cls.seoul,
            division=cls.div,
        )
        cls.female_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="201",
            capacity=2,
            recommended_gender=LodgingRoom.Gender.FEMALE,
            region=cls.seoul,
            division=cls.div,
        )
        cls.other_lodging = Lodging.objects.create(
            event=cls.other_event, name="외부 숙소"
        )
        cls.other_room = LodgingRoom.objects.create(
            lodging=cls.other_lodging,
            number="X1",
            region=cls.seoul,
            division=cls.div,
        )
        cls.male_attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="남자A",
            gender=RetreatAttendee.Gender.MALE,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            expected_check_in_at=timezone.now(),
        )
        cls.male_attendee_b = RetreatAttendee.objects.create(
            group=cls.group,
            name="남자B",
            gender=RetreatAttendee.Gender.MALE,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            expected_check_in_at=timezone.now(),
        )
        cls.male_attendee_c = RetreatAttendee.objects.create(
            group=cls.group,
            name="남자C",
            gender=RetreatAttendee.Gender.MALE,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            expected_check_in_at=timezone.now(),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.leader)

    def _detail(self, attendee):
        return reverse("api_retreat_attendee_detail", args=[attendee.id])

    def test_assign_room_ok(self):
        r = self.client.patch(
            self._detail(self.male_attendee),
            {"lodging_room": self.room.id},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.male_attendee.refresh_from_db()
        self.assertEqual(self.male_attendee.lodging_room_id, self.room.id)

    def test_clear_room_with_null(self):
        self.male_attendee.lodging_room = self.room
        self.male_attendee.save(update_fields=["lodging_room"])
        r = self.client.patch(
            self._detail(self.male_attendee),
            {"lodging_room": None},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.male_attendee.refresh_from_db()
        self.assertIsNone(self.male_attendee.lodging_room_id)

    def test_capacity_overflow_rejected(self):
        r1 = self.client.patch(
            self._detail(self.male_attendee),
            {"lodging_room": self.room.id},
            format="json",
        )
        self.assertEqual(r1.status_code, 200, r1.content)
        r2 = self.client.patch(
            self._detail(self.male_attendee_b),
            {"lodging_room": self.room.id},
            format="json",
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        # 정원 2명인데 추가로 한 명 더 배정 → 400
        r = self.client.patch(
            self._detail(self.male_attendee_c),
            {"lodging_room": self.room.id},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)

    def test_checked_out_in_room_does_not_block_new_assignment(self):
        """퇴실(ended) 조원은 정원 집계에서 제외되어 새 배정이 가능해야 한다."""
        from retreat.services.lodging_stay import persist_lodging_stay_status

        checked_out = RetreatAttendee.objects.create(
            group=self.group,
            name="퇴실자",
            gender=RetreatAttendee.Gender.MALE,
            expected_check_in_at=timezone.now(),
            lodging_room=self.room,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        persist_lodging_stay_status(checked_out)
        checked_out.refresh_from_db()
        self.assertEqual(
            checked_out.lodging_stay_status,
            RetreatAttendee.LodgingStayStatus.ENDED,
        )

        r = self.client.patch(
            self._detail(self.male_attendee),
            {"lodging_room": self.room.id},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.male_attendee.refresh_from_db()
        self.assertEqual(self.male_attendee.lodging_room_id, self.room.id)

    def test_gender_mismatch_rejected(self):
        r = self.client.patch(
            self._detail(self.male_attendee),
            {"lodging_room": self.female_room.id},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)

    def test_assign_room_validates_with_patched_gender(self):
        attendee = RetreatAttendee.objects.create(group=self.group, name="미지정")
        self.client.force_authenticate(self.staff)
        r = self.client.patch(
            self._detail(attendee),
            {
                "gender": RetreatAttendee.Gender.MALE,
                "lodging_room": self.male_room.id,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        attendee.refresh_from_db()
        self.assertEqual(attendee.gender, RetreatAttendee.Gender.MALE)
        self.assertEqual(attendee.lodging_room_id, self.male_room.id)

    def test_other_event_room_rejected(self):
        r = self.client.patch(
            self._detail(self.male_attendee),
            {"lodging_room": self.other_room.id},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)


class LodgingAssignmentPickerTests(LodgingRoomAssignmentTests):
    """배정 드롭다운 노출 필터."""

    def test_room_visible_hides_full_and_gender_mismatch(self):
        from retreat.services.lodging import (
            room_visible_in_assignment_picker,
            rooms_for_group_with_counts,
        )
        from retreat.services.lodging_stay import persist_lodging_stay_status

        self.male_attendee.lodging_room = self.room
        self.male_attendee.save(update_fields=["lodging_room"])
        persist_lodging_stay_status(self.male_attendee)
        self.male_attendee_b.lodging_room = self.room
        self.male_attendee_b.save(update_fields=["lodging_room"])
        persist_lodging_stay_status(self.male_attendee_b)

        rooms = list(rooms_for_group_with_counts(self.group))
        room_by_number = {r.number: r for r in rooms}

        self.assertFalse(
            room_visible_in_assignment_picker(
                room_by_number["101"],
                gender=RetreatAttendee.Gender.MALE,
            )
        )
        self.assertTrue(
            room_visible_in_assignment_picker(
                room_by_number["101"],
                gender=RetreatAttendee.Gender.MALE,
                current_room_id=self.room.id,
            )
        )
        self.assertFalse(
            room_visible_in_assignment_picker(
                room_by_number["201"],
                gender=RetreatAttendee.Gender.MALE,
            )
        )
        self.assertTrue(
            room_visible_in_assignment_picker(
                room_by_number["102"],
                gender=RetreatAttendee.Gender.MALE,
            )
        )

    def test_room_assignment_option_includes_counts(self):
        from retreat.services.lodging import (
            room_assignment_option,
            rooms_for_group_with_counts,
        )
        from retreat.services.lodging_stay import persist_lodging_stay_status

        self.male_attendee.lodging_room = self.male_room
        self.male_attendee.save(update_fields=["lodging_room"])
        persist_lodging_stay_status(self.male_attendee)
        room = rooms_for_group_with_counts(self.group).get(pk=self.male_room.id)
        opt = room_assignment_option(room)
        self.assertEqual(opt["assigned_count"], 1)
        self.assertEqual(opt["recommended_gender"], "male")
        self.assertEqual(opt["capacity"], 2)


class LodgingRoomScopeTests(_LodgingFixture):
    """LodgingRoom 의 region/division 매칭: 조의 region+division 과 같은 호실만 허용."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.incheon, _ = Region.objects.get_or_create(
            code="incheon", defaults={"name": "인천", "sort_order": 20}
        )
        cls.other_div = Division.objects.create(
            region=cls.seoul, code="lodging_college", name="대학부"
        )
        cls.lodging = Lodging.objects.create(
            event=cls.event, name="본관", region=cls.seoul
        )
        cls.same_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="101",
            capacity=4,
            region=cls.seoul,
            division=cls.div,
        )
        cls.other_region_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="201",
            capacity=4,
            region=cls.incheon,
            division=cls.div,
        )
        cls.other_division_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="301",
            capacity=4,
            region=cls.seoul,
            division=cls.other_div,
        )
        cls.unassigned_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="401",
            capacity=4,
        )
        cls.attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="서울 청년",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.leader)

    def _detail(self, attendee):
        return reverse("api_retreat_attendee_detail", args=[attendee.id])

    def test_same_region_and_division_room_ok(self):
        r = self.client.patch(
            self._detail(self.attendee),
            {"lodging_room": self.same_room.id},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)

    def test_other_region_room_rejected(self):
        r = self.client.patch(
            self._detail(self.attendee),
            {"lodging_room": self.other_region_room.id},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)

    def test_other_division_room_rejected(self):
        r = self.client.patch(
            self._detail(self.attendee),
            {"lodging_room": self.other_division_room.id},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)

    def test_unassigned_room_rejected(self):
        """호실의 region 또는 division 이 비어있으면 어떤 조에도 배정 불가."""
        r = self.client.patch(
            self._detail(self.attendee),
            {"lodging_room": self.unassigned_room.id},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)


class ManageGroupRoomOptionsTests(_LodgingFixture):
    """조 관리 페이지의 event_rooms 가 조의 region+division 매칭 호실만 노출."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_div = Division.objects.create(
            region=cls.seoul, code="lodging_other", name="청년1부"
        )
        cls.lodging = Lodging.objects.create(
            event=cls.event, name="본관", region=cls.seoul
        )
        cls.matching_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="A",
            region=cls.seoul,
            division=cls.div,
        )
        cls.other_div_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="B",
            region=cls.seoul,
            division=cls.other_div,
        )
        cls.unassigned_room = LodgingRoom.objects.create(
            lodging=cls.lodging, number="C"
        )

    def setUp(self):
        self.client = APIClient()

    def test_event_rooms_filtered_by_region_and_division(self):
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse("retreat_group_manage", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)
        room_ids = {room["id"] for room in r.context["event_rooms"]}
        self.assertIn(self.matching_room.id, room_ids)
        self.assertNotIn(self.other_div_room.id, room_ids)
        self.assertNotIn(self.unassigned_room.id, room_ids)


class LodgingAssignRedirectTests(_LodgingFixture):
    """구 방배정 URL → 숙소·호수 관리 리다이렉트."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.lodging = Lodging.objects.create(
            event=cls.event, name="본관", region=cls.seoul
        )
        cls.matching_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="A",
            region=cls.seoul,
            division=cls.div,
        )

    def setUp(self):
        self.client = APIClient()

    def _lodging_url(self):
        return reverse("retreat_lodging", args=[self.event.id])

    def test_assign_url_redirects_to_lodging_page(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("retreat_lodging_assign", args=[self.event.id])
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], self._lodging_url())

    def test_lodging_page_lists_rooms_by_lodging(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._lodging_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "본관")
        self.assertContains(r, self.matching_room.number)
        self.assertNotContains(r, "숙소별")
        self.assertNotContains(r, "지역·부서별")
        self.assertNotContains(r, "방배정")
        self.assertContains(r, 'id="lodgingManageFilterBar"')
        self.assertContains(r, ">정원</span>")
        self.assertContains(r, 'data-lodging-filter="vacancy"')
        self.assertContains(r, "잔여 객실")
        self.assertContains(r, 'data-lodging-filter="full"')
        self.assertContains(r, ">만실</button>")
        self.assertContains(r, 'data-lodging-filter-preset="vacancy"')
        self.assertContains(r, 'id="lodgingVacancyFilterEmpty"')
        self.assertContains(r, "선택한 조건에 맞는 객실이 없습니다.")
        self.assertContains(r, "lodging_manage_filter.js")

    def test_leader_blocked_from_lodging_page(self):
        self.client.force_login(self.leader)
        r = self.client.get(self._lodging_url())
        self.assertEqual(r.status_code, 403)


class LodgingVacancyAttributeTests(_LodgingFixture):
    """호실 행 data-room-has-vacancy 속성."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.lodging = Lodging.objects.create(event=cls.event, name="본관")
        cls.vacant_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="101",
            capacity=2,
            region=cls.seoul,
            division=cls.div,
        )
        cls.full_room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="102",
            capacity=1,
            region=cls.seoul,
            division=cls.div,
        )
        attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="배정자",
            expected_check_in_at=timezone.now(),
        )
        attendee.lodging_room = cls.full_room
        attendee.save(update_fields=["lodging_room"])
        from retreat.services.lodging_stay import persist_lodging_stay_status

        persist_lodging_stay_status(attendee)

    def setUp(self):
        self.client = APIClient()

    def test_room_has_vacancy_data_attributes(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("retreat_lodging", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(
            r,
            f'data-room-id="{self.vacant_room.id}"',
        )
        self.assertContains(
            r,
            f'data-room-id="{self.vacant_room.id}" data-lodging-id="{self.lodging.id}"',
        )
        content = r.content.decode()
        vacant_idx = content.find(f'data-room-id="{self.vacant_room.id}"')
        full_idx = content.find(f'data-room-id="{self.full_room.id}"')
        self.assertGreater(vacant_idx, -1)
        self.assertGreater(full_idx, -1)
        vacant_snippet = content[vacant_idx : vacant_idx + 280]
        full_snippet = content[full_idx : full_idx + 280]
        self.assertIn('data-room-has-vacancy="1"', vacant_snippet)
        self.assertIn('data-room-has-vacancy="0"', full_snippet)


class LodgingRoomMappingApiTests(_LodgingFixture):
    """호실 region/division PATCH — 조회 전용 뷰와 별도 API 권한."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_div = Division.objects.create(
            region=cls.seoul, code="lodging_map_other", name="대학부"
        )
        cls.lodging = Lodging.objects.create(event=cls.event, name="본관")
        cls.room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="A",
            region=cls.seoul,
            division=cls.div,
        )

    def setUp(self):
        self.client = APIClient()

    def test_staff_can_remap_room_to_other_division(self):
        self.client.force_authenticate(self.staff)
        room_detail = reverse("api_retreat_lodging_room_detail", args=[self.room.id])
        r = self.client.patch(
            room_detail,
            {"division": self.other_div.id},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.room.refresh_from_db()
        self.assertEqual(self.room.division_id, self.other_div.id)

    def test_staff_can_unassign_room(self):
        self.client.force_authenticate(self.staff)
        room_detail = reverse("api_retreat_lodging_room_detail", args=[self.room.id])
        r = self.client.patch(
            room_detail,
            {"region": None, "division": None},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.room.refresh_from_db()
        self.assertIsNone(self.room.region_id)
        self.assertIsNone(self.room.division_id)

    def test_leader_cannot_remap_room(self):
        self.client.force_authenticate(self.leader)
        room_detail = reverse("api_retreat_lodging_room_detail", args=[self.room.id])
        r = self.client.patch(
            room_detail,
            {"division": self.other_div.id},
            format="json",
        )
        self.assertEqual(r.status_code, 403)


class LodgingCrudPageRedirectTests(_LodgingFixture):
    """기존 `/lodgings/` 페이지가 staff/leader/outsider 에게 어떻게 응답하는지."""

    def setUp(self):
        self.client = APIClient()

    def _url(self):
        return reverse("retreat_lodging", args=[self.event.id])

    def test_staff_ok(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_lodging"])
        self.assertNotContains(r, "방배정")

    def test_leader_blocked(self):
        # 숙소 탭은 회장단·운영진·슈퍼유저 전용. 조장/부조장은 접근 불가.
        self.client.force_login(self.leader)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)

    def test_outsider_blocked(self):
        self.client.force_login(self.outsider)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)
