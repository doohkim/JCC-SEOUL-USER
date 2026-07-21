"""수련회 픽업(입회/출회) 권한·CRUD 테스트."""

from __future__ import annotations

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatPickup,
)
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


def _tt(hour, minute=0):
    """테스트용 열차 시각(Asia/Seoul aware datetime)."""
    return timezone.make_aware(datetime(2026, 8, 1, hour, minute))


class _PickupFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="pickup_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="픽업 테스트",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.group2 = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="2조",
        )

        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president",
            defaults={"name": "회장", "level": 80, "sort_order": 20},
        )

        cls.superuser = User.objects.create_superuser(
            username="pickup_super", password="x"
        )

        cls.council = User.objects.create_user(username="pickup_council", password="x")
        UserDivisionTeam.objects.create(
            user=cls.council, division=cls.div, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

        cls.leader = User.objects.create_user(username="pickup_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.staff = User.objects.create_user(username="pickup_staff", password="x")
        cls.staff.role_level = cls.rl_president
        cls.staff.save()
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.div, is_primary=True
        )

        cls.stranger = User.objects.create_user(
            username="pickup_stranger", password="x"
        )

    def _attendee(self, group, name, **kwargs):
        return RetreatAttendee.objects.create(group=group, name=name, **kwargs)

    def setUp(self):
        self.client = APIClient()
        self.page_client = Client()


class PickupPageTests(_PickupFixture):
    def _url(self, tab="arrival"):
        return reverse("retreat_pickup", args=[self.event.id]) + f"?tab={tab}"

    def test_leader_can_view_pickup_page(self):
        self.page_client.force_login(self.leader)
        r = self.page_client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_pickup"])
        self.assertFalse(r.context["can_select_pickup_group"])
        self.assertEqual(r.context["leader_group_id"], self.group.id)
        self.assertEqual(r.context["leader_group_ids"], [self.group.id])
        self.assertContains(r, "입회")
        self.assertContains(r, "data-leader-member-select")
        self.assertNotContains(r, "data-leader-group-select")

    @override_settings(
        STORAGES={
            "default": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            },
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
    )
    def test_multi_group_leader_sees_group_select_and_both_rosters(self):
        RetreatGroupMembership.objects.create(user=self.leader, group=self.group2)
        self._attendee(self.group, "일조원")
        self._attendee(self.group2, "이조원")
        self.page_client.force_login(self.leader)
        r = self.page_client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            set(r.context["leader_group_ids"]), {self.group.id, self.group2.id}
        )
        self.assertContains(r, "data-leader-group-select")
        members = r.context["pickup_group_members_json"]
        self.assertIn("일조원", members)
        self.assertIn("이조원", members)

    def test_council_can_view_pickup_page(self):
        self.page_client.force_login(self.council)
        r = self.page_client.get(self._url("departure"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_pickup"])
        self.assertContains(r, "출회")

    def test_stranger_forbidden(self):
        self.page_client.force_login(self.stranger)
        r = self.page_client.get(self._url())
        self.assertEqual(r.status_code, 403)


class PickupApiTests(_PickupFixture):
    def _list_url(self):
        return reverse("api_retreat_event_pickups", args=[self.event.id])

    def _detail_url(self, pickup_id):
        return reverse("api_retreat_pickup_detail", args=[pickup_id])

    def test_leader_can_create_pickup_with_auto_number(self):
        self._attendee(self.group, "홍길동")
        self._attendee(self.group, "김철수")
        self.client.force_login(self.leader)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "홍길동",
                "region": self.seoul.id,
                "division": self.div.id,
                "train_time": "2026-08-01T10:38",
                "boarding_place": "장성역",
                "contact": "010-1234-5678",
                "note": "",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["number"], 1)
        self.assertEqual(r.data["name"], "홍길동")
        self.assertEqual(r.data["region"], self.seoul.id)
        self.assertEqual(r.data["division"], self.div.id)
        self.assertEqual(r.data["division_name"], self.div.name)
        # 조장은 조를 선택하지 못하고 본인 조로 자동 지정 + 신청자 기록
        self.assertEqual(r.data["group"], self.group.id)
        self.assertEqual(r.data["applicant_name"], self.leader.get_username())

        r2 = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "김철수",
                "train_time": "2026-08-01T11:00",
                "boarding_place": "장성역",
                "contact": "010-9999-8888",
            },
            format="json",
        )
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r2.data["number"], 2)

    def test_multi_group_leader_can_create_pickup_for_second_group(self):
        RetreatGroupMembership.objects.create(user=self.leader, group=self.group2)
        self._attendee(self.group2, "이조원")
        self.client.force_login(self.leader)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "group": self.group2.id,
                "name": "이조원",
                "train_time": "2026-08-01T11:00",
                "boarding_place": "장성역",
                "contact": "010-2222-3333",
                "note": "",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["group"], self.group2.id)
        self.assertEqual(r.data["name"], "이조원")

    def test_multi_group_leader_cannot_create_pickup_for_other_group(self):
        RetreatGroupMembership.objects.create(user=self.leader, group=self.group2)
        other = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="3조",
        )
        self._attendee(other, "삼조원")
        self.client.force_login(self.leader)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "group": other.id,
                "name": "삼조원",
                "train_time": "2026-08-01T11:00",
                "boarding_place": "장성역",
                "contact": "010-2222-3333",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)

    def test_duplicate_pickup_same_group_name_rejected(self):
        self._attendee(self.group, "김비투")
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="김비투",
            train_time=_tt(17, 20),
            boarding_place="장성역",
            contact="010-4442-1313",
        )
        self.client.force_login(self.leader)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "김비투",
                "train_time": "2026-08-01T17:20",
                "boarding_place": "장성역",
                "contact": "010-4442-1313",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("name", r.data)
        self.assertEqual(
            RetreatPickup.objects.filter(
                event=self.event,
                direction=RetreatPickup.Direction.ARRIVAL,
                group=self.group,
                name="김비투",
            ).count(),
            1,
        )

    def test_same_name_different_direction_allowed(self):
        self._attendee(
            self.group,
            "김비투",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="김비투",
            train_time=_tt(17, 20),
            boarding_place="장성역",
            contact="010-4442-1313",
        )
        self.client.force_login(self.leader)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.DEPARTURE,
                "name": "김비투",
                "train_time": "2026-08-03T10:00",
                "boarding_place": "장성역",
                "contact": "010-4442-1313",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)

    def test_create_requires_mandatory_fields(self):
        self._attendee(self.group, "이름만")
        self.client.force_login(self.council)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.DEPARTURE,
                "name": "이름만",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("train_time", r.data)

    def test_staff_without_membership_cannot_create(self):
        self.client.force_login(self.staff)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "테스트",
                "train_time": "2026-08-01T09:00",
                "boarding_place": "역",
                "contact": "010-0000-0000",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_leader_can_list_pickups(self):
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="기존",
            train_time=_tt(8, 0),
            boarding_place="역",
            contact="010-1111-2222",
        )
        self.client.force_login(self.leader)
        r = self.client.get(
            self._list_url(),
            {"direction": RetreatPickup.Direction.ARRIVAL},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_stranger_cannot_list_pickups(self):
        self.client.force_login(self.stranger)
        r = self.client.get(
            self._list_url(),
            {"direction": RetreatPickup.Direction.ARRIVAL},
        )
        self.assertEqual(r.status_code, 403)

    def test_council_can_delete_pickup(self):
        pickup = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            name="삭제대상",
            train_time=_tt(12, 0),
            boarding_place="터미널",
            contact="010-3333-4444",
        )
        self.client.force_login(self.council)
        r = self.client.delete(self._detail_url(pickup.id))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(RetreatPickup.objects.filter(pk=pickup.id).exists())

    def test_staff_without_membership_cannot_delete(self):
        pickup = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            name="삭제불가",
            train_time=_tt(12, 0),
            boarding_place="터미널",
            contact="010-5555-6666",
        )
        self.client.force_login(self.staff)
        r = self.client.delete(self._detail_url(pickup.id))
        self.assertEqual(r.status_code, 403)

    def test_leader_group_is_forced_to_own_group(self):
        """조장이 다른 조 id 를 보내도 무시되고 본인 조로 저장된다."""
        self._attendee(self.group, "강제조")
        self.client.force_login(self.leader)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "강제조",
                "group": self.group2.id,
                "train_time": "2026-08-01T07:00",
                "boarding_place": "역",
                "contact": "010-0000-1111",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["group"], self.group.id)

    def test_leader_lists_only_own_group(self):
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="내조",
            train_time=_tt(8),
            boarding_place="역",
            contact="010-1111-2222",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=2,
            group=self.group2,
            name="남의조",
            train_time=_tt(9),
            boarding_place="역",
            contact="010-3333-4444",
        )
        self.client.force_login(self.leader)
        r = self.client.get(
            self._list_url(), {"direction": RetreatPickup.Direction.ARRIVAL}
        )
        self.assertEqual(r.status_code, 200)
        names = {row["name"] for row in r.data}
        self.assertEqual(names, {"내조"})

    def test_council_lists_all_groups(self):
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="A",
            train_time=_tt(8),
            boarding_place="역",
            contact="010-1111-2222",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=2,
            group=self.group2,
            name="B",
            train_time=_tt(9),
            boarding_place="역",
            contact="010-3333-4444",
        )
        self.client.force_login(self.council)
        r = self.client.get(
            self._list_url(), {"direction": RetreatPickup.Direction.ARRIVAL}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_council_can_select_group(self):
        self._attendee(
            self.group2,
            "회장선택",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        self.client.force_login(self.council)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.DEPARTURE,
                "name": "회장선택",
                "group": self.group2.id,
                "train_time": "2026-08-03T18:00",
                "boarding_place": "터미널",
                "contact": "010-7777-8888",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["group"], self.group2.id)

    def test_leader_cannot_create_pickup_for_non_roster_name(self):
        self.client.force_login(self.leader)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "명단외",
                "train_time": "2026-08-01T10:00",
                "boarding_place": "역",
                "contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("name", r.data)

    def test_council_cannot_create_pickup_for_non_roster_name(self):
        self.client.force_login(self.council)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "명단외",
                "group": self.group.id,
                "train_time": "2026-08-01T10:00",
                "boarding_place": "역",
                "contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("name", r.data)

    def test_absent_attendee_cannot_be_pickup_target(self):
        self._attendee(
            self.group,
            "불참자",
            participation_status=RetreatAttendee.ParticipationStatus.ABSENT,
        )
        self.client.force_login(self.leader)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "불참자",
                "train_time": "2026-08-01T10:00",
                "boarding_place": "역",
                "contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("name", r.data)

    def test_arrival_rejects_checked_in_attendee(self):
        self._attendee(
            self.group,
            "입실자",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        self.client.force_login(self.council)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "입실자",
                "group": self.group.id,
                "train_time": "2026-08-01T10:00",
                "boarding_place": "역",
                "contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("name", r.data)

    def test_departure_rejects_pending_attendee(self):
        self._attendee(self.group, "입실전")
        self.client.force_login(self.council)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.DEPARTURE,
                "name": "입실전",
                "group": self.group.id,
                "train_time": "2026-08-01T10:00",
                "boarding_place": "역",
                "contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("name", r.data)

    def test_departure_accepts_checked_in_attendee(self):
        self._attendee(
            self.group,
            "출회대상",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        self.client.force_login(self.council)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.DEPARTURE,
                "name": "출회대상",
                "group": self.group.id,
                "train_time": "2026-08-01T10:00",
                "boarding_place": "역",
                "contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)

    def test_leader_cannot_delete_other_group_pickup(self):
        pickup = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group2,
            name="남의조",
            train_time=_tt(12),
            boarding_place="터미널",
            contact="010-5555-6666",
        )
        self.client.force_login(self.leader)
        r = self.client.delete(self._detail_url(pickup.id))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(RetreatPickup.objects.filter(pk=pickup.id).exists())

    def test_leader_region_division_forced_from_group(self):
        """조장이 다른 지역·부서를 보내도 본인 조의 지역·부서로 저장된다."""
        self._attendee(self.group, "지역강제")
        other_div = Division.objects.create(
            region=self.seoul, code="pickup_other", name="기타부"
        )
        self.client.force_login(self.leader)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "지역강제",
                "region": self.seoul.id,
                "division": other_div.id,
                "train_time": "2026-08-01T07:00",
                "boarding_place": "역",
                "contact": "010-0000-1111",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["region"], self.group.region_id)
        self.assertEqual(r.data["division"], self.group.division_id)

    def test_invalid_phone_rejected(self):
        self._attendee(self.group, "잘못된번호")
        self.client.force_login(self.council)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "잘못된번호",
                "train_time": "2026-08-01T10:00",
                "boarding_place": "역",
                "contact": "9123123",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("contact", r.data)

    def test_phone_is_normalized(self):
        self._attendee(self.group, "정규화")
        self.client.force_login(self.council)
        r = self.client.post(
            self._list_url(),
            {
                "direction": RetreatPickup.Direction.ARRIVAL,
                "name": "정규화",
                "train_time": "2026-08-01T10:00",
                "boarding_place": "역",
                "contact": "01012345678",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["contact"], "010-1234-5678")

    def test_leader_can_edit_own_pickup(self):
        self._attendee(self.group, "수정전")
        self._attendee(self.group, "수정후")
        pickup = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="수정전",
            train_time=_tt(8),
            boarding_place="역",
            contact="010-1111-2222",
        )
        self.client.force_login(self.leader)
        r = self.client.patch(
            self._detail_url(pickup.id),
            {"name": "수정후", "contact": "01099998888"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["name"], "수정후")
        self.assertEqual(r.data["contact"], "010-9999-8888")
        pickup.refresh_from_db()
        self.assertEqual(pickup.name, "수정후")

    def test_edit_rejects_invalid_phone(self):
        pickup = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="수정",
            train_time=_tt(8),
            boarding_place="역",
            contact="010-1111-2222",
        )
        self.client.force_login(self.leader)
        r = self.client.patch(
            self._detail_url(pickup.id),
            {"contact": "abc"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("contact", r.data)

    def test_leader_cannot_edit_other_group_pickup(self):
        pickup = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group2,
            name="남의조",
            train_time=_tt(8),
            boarding_place="역",
            contact="010-1111-2222",
        )
        self.client.force_login(self.leader)
        r = self.client.patch(
            self._detail_url(pickup.id),
            {"name": "침범"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)
        pickup.refresh_from_db()
        self.assertEqual(pickup.name, "남의조")

    def test_council_can_edit_group(self):
        self._attendee(self.group, "조변경")
        self._attendee(self.group2, "조변경")
        pickup = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="조변경",
            train_time=_tt(8),
            boarding_place="역",
            contact="010-1111-2222",
        )
        self.client.force_login(self.council)
        r = self.client.patch(
            self._detail_url(pickup.id),
            {"group": self.group2.id},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["group"], self.group2.id)


class AttendeeDeletePickupCascadeTests(_PickupFixture):
    """조원 삭제 시 동일 조·이름 픽업 요청 연쇄 삭제."""

    def setUp(self):
        super().setUp()
        self.attendee = RetreatAttendee.objects.create(
            group=self.group,
            name="픽업대상",
        )
        self.pickup_arrival = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="픽업대상",
            train_time=_tt(9),
            boarding_place="서울역",
            contact="010-1111-2222",
        )
        self.pickup_departure = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.DEPARTURE,
            number=1,
            group=self.group,
            name="픽업대상",
            train_time=_tt(18),
            boarding_place="수원역",
            contact="010-1111-2222",
        )
        self.other_pickup = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=2,
            group=self.group,
            name="다른사람",
            train_time=_tt(10),
            boarding_place="역",
            contact="010-3333-4444",
        )
        self.url = reverse("api_retreat_attendee_detail", args=[self.attendee.id])

    def test_get_with_pickups_lists_linked_requests(self):
        self.client.force_authenticate(self.leader)
        r = self.client.get(f"{self.url}?with_pickups=1")
        self.assertEqual(r.status_code, 200, r.content)
        pickups = r.data.get("linked_pickups") or []
        self.assertEqual(len(pickups), 2)
        numbers = {p["number"] for p in pickups}
        self.assertEqual(numbers, {1})

    def test_delete_attendee_removes_matching_pickups_only(self):
        self.client.force_authenticate(self.leader)
        r = self.client.delete(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data.get("deleted_pickup_count"), 2)
        self.assertFalse(RetreatAttendee.objects.filter(pk=self.attendee.id).exists())
        self.assertFalse(
            RetreatPickup.objects.filter(
                pk__in=[self.pickup_arrival.id, self.pickup_departure.id]
            ).exists()
        )
        self.assertTrue(RetreatPickup.objects.filter(pk=self.other_pickup.id).exists())
