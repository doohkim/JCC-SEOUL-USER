"""숙소·호실 모델·API·배정 검증 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from retreat.models import (
    Lodging,
    LodgingRoom,
    RetreatAttendee,
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
            name="숙소 행사",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.other_event = RetreatEvent.objects.create(
            name="다른 행사",
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

    def test_leader_can_list_lodgings(self):
        Lodging.objects.create(event=self.event, name="본관")
        self.client.force_authenticate(self.leader)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)

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
        )
        cls.male_attendee_b = RetreatAttendee.objects.create(
            group=cls.group,
            name="남자B",
            gender=RetreatAttendee.Gender.MALE,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.male_attendee_c = RetreatAttendee.objects.create(
            group=cls.group,
            name="남자C",
            gender=RetreatAttendee.Gender.MALE,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
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
        self.male_attendee.lodging_room = self.room
        self.male_attendee.save(update_fields=["lodging_room"])
        self.male_attendee_b.lodging_room = self.room
        self.male_attendee_b.save(update_fields=["lodging_room"])
        # 정원 2명인데 추가로 한 명 더 배정 → 400
        r = self.client.patch(
            self._detail(self.male_attendee_c),
            {"lodging_room": self.room.id},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)

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
        room_ids = {room.id for room in r.context["event_rooms"]}
        self.assertIn(self.matching_room.id, room_ids)
        self.assertNotIn(self.other_div_room.id, room_ids)
        self.assertNotIn(self.unassigned_room.id, room_ids)


class LodgingAssignPageTests(_LodgingFixture):
    """방배정 페이지 GET + 권한 분기.

    이 페이지는 호실 → 지역·부서 매핑 관리용이다. 카드 본문에는 (region, division)
    조합이 노출되고, 미배정 호실은 별도 섹션으로 묶인다.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_div = Division.objects.create(
            region=cls.seoul, code="lodging_assign_other", name="대학부"
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
        cls.unassigned_room = LodgingRoom.objects.create(
            lodging=cls.lodging, number="Z"
        )

    def setUp(self):
        self.client = APIClient()

    def _url(self):
        return reverse("retreat_lodging_assign", args=[self.event.id])

    def test_staff_sees_assign_page(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "방배정")
        self.assertTrue(r.context["is_staff_like"])
        self.assertTrue(r.context["can_manage_lodging"])

    def test_leader_blocked_from_assign_page(self):
        # 숙소(방배정)는 회장단·운영진·슈퍼유저 전용. 조장/부조장은 접근 불가.
        self.client.force_login(self.leader)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)

    def test_outsider_blocked(self):
        self.client.force_login(self.outsider)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)

    def test_regions_grouped_with_assigned_room(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        region_ids = {b["region"].id for b in r.context["regions"]}
        self.assertIn(self.seoul.id, region_ids)
        # 서울 카드 안에 div 부서가 있고, 호실 A 가 들어있어야 함.
        seoul_bucket = next(
            b for b in r.context["regions"] if b["region"].id == self.seoul.id
        )
        div_ids = {d["division"].id for d in seoul_bucket["divisions"]}
        self.assertIn(self.div.id, div_ids)
        target = next(
            d for d in seoul_bucket["divisions"] if d["division"].id == self.div.id
        )
        room_ids = {room.id for room in target["rooms"]}
        self.assertIn(self.matching_room.id, room_ids)
        self.assertNotIn(self.unassigned_room.id, room_ids)
        unassigned_ids = {room.id for room in r.context["unassigned_rooms"]}
        self.assertIn(self.unassigned_room.id, unassigned_ids)

    def test_staff_can_remap_room_to_other_division(self):
        self.client.force_login(self.staff)
        room_detail = reverse(
            "api_retreat_lodging_room_detail", args=[self.matching_room.id]
        )
        r = self.client.patch(
            room_detail,
            {"division": self.other_div.id},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.matching_room.refresh_from_db()
        self.assertEqual(self.matching_room.division_id, self.other_div.id)

    def test_staff_can_unassign_room(self):
        self.client.force_login(self.staff)
        room_detail = reverse(
            "api_retreat_lodging_room_detail", args=[self.matching_room.id]
        )
        r = self.client.patch(
            room_detail,
            {"region": None, "division": None},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.matching_room.refresh_from_db()
        self.assertIsNone(self.matching_room.region_id)
        self.assertIsNone(self.matching_room.division_id)

    def test_leader_cannot_remap_room(self):
        self.client.force_login(self.leader)
        room_detail = reverse(
            "api_retreat_lodging_room_detail", args=[self.matching_room.id]
        )
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
        # 서브탭 링크 노출 — 방배정.
        self.assertContains(r, reverse("retreat_lodging_assign", args=[self.event.id]))

    def test_leader_blocked(self):
        # 숙소 탭은 회장단·운영진·슈퍼유저 전용. 조장/부조장은 접근 불가.
        self.client.force_login(self.leader)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)

    def test_outsider_blocked(self):
        self.client.force_login(self.outsider)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)
