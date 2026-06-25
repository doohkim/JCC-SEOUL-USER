"""수련회 권한 격리 + 그룹 가시성 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatGroupScope,
)
from users.models import (
    Division,
    PastoralDivisionAssignment,
    Region,
    Role,
    RoleLevel,
    UserDivisionTeam,
    UserFunctionalDeptRole,
    FunctionalDepartment,
)
from users.permissions import (
    can_access_retreat_tab,
    can_change_retreat_check_in,
    can_view_retreat_all,
    is_retreat_group_leader,
    is_retreat_staff,
    visible_retreat_groups_for,
)

User = get_user_model()


class _BaseFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.incheon, _ = Region.objects.get_or_create(
            code="incheon", defaults={"name": "인천", "sort_order": 20}
        )
        cls.div_youth_seoul = Division.objects.create(
            region=cls.seoul, code="t_seoul_youth_r", name="청년부"
        )
        cls.div_univ_seoul = Division.objects.create(
            region=cls.seoul, code="t_seoul_univ_r", name="대학부"
        )
        cls.div_youth_incheon = Division.objects.create(
            region=cls.incheon, code="t_incheon_youth_r", name="청년부"
        )

        cls.event = RetreatEvent.objects.create(
            name="2026 전국 수련회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.group_seoul_1 = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_youth_seoul,
            name="1조",
            order=1,
        )
        cls.group_seoul_2 = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_youth_seoul,
            name="2조",
            order=2,
        )
        cls.group_incheon_1 = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.incheon,
            division=cls.div_youth_incheon,
            name="인천 1조",
            order=1,
        )

        # 조장: 서울 1조
        cls.leader_seoul_1 = User.objects.create_user(
            username="leader_seoul_1", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.leader_seoul_1, division=cls.div_youth_seoul, is_primary=True
        )
        RetreatGroupMembership.objects.create(
            user=cls.leader_seoul_1,
            group=cls.group_seoul_1,
            role=RetreatGroupMembership.Role.LEADER,
        )

        # 조장: 서울 2조 (다른 조)
        cls.leader_seoul_2 = User.objects.create_user(
            username="leader_seoul_2", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.leader_seoul_2, division=cls.div_youth_seoul, is_primary=True
        )
        RetreatGroupMembership.objects.create(
            user=cls.leader_seoul_2,
            group=cls.group_seoul_2,
            role=RetreatGroupMembership.Role.LEADER,
        )

        # 조장: 인천 1조
        cls.leader_incheon = User.objects.create_user(
            username="leader_incheon", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.leader_incheon, division=cls.div_youth_incheon, is_primary=True
        )
        RetreatGroupMembership.objects.create(
            user=cls.leader_incheon,
            group=cls.group_incheon_1,
            role=RetreatGroupMembership.Role.LEADER,
        )

        # staff: 서울 청년부 회장 (RoleLevel = president)
        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president", defaults={"name": "회장", "level": 80, "sort_order": 20}
        )
        cls.staff_seoul = User.objects.create_user(
            username="staff_seoul", password="x"
        )
        cls.staff_seoul.role_level = cls.rl_president
        cls.staff_seoul.save()
        UserDivisionTeam.objects.create(
            user=cls.staff_seoul, division=cls.div_youth_seoul, is_primary=True
        )

        # staff: 부장(Role) 권한자 (서울 대학부)
        cls.role_dept_head, _ = Role.objects.get_or_create(
            code="dept_head", defaults={"name": "부장", "sort_order": 10}
        )
        cls.func_dept_praise, _ = FunctionalDepartment.objects.get_or_create(
            code="praise", defaults={"name": "찬양단"}
        )
        cls.staff_univ = User.objects.create_user(
            username="staff_univ_seoul", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.staff_univ, division=cls.div_univ_seoul, is_primary=True
        )
        UserFunctionalDeptRole.objects.create(
            user=cls.staff_univ,
            functional_department=cls.func_dept_praise,
            role=cls.role_dept_head,
        )

        cls.rl_pastor, _ = RoleLevel.objects.get_or_create(
            code="pastor", defaults={"name": "목사", "level": 80, "sort_order": 10}
        )
        cls.pastor = User.objects.create_user(username="pastor_r", password="x")
        cls.pastor.role_level = cls.rl_pastor
        cls.pastor.save()
        UserDivisionTeam.objects.create(
            user=cls.pastor, division=cls.div_youth_seoul, is_primary=True
        )
        PastoralDivisionAssignment.objects.create(
            user=cls.pastor, division=cls.div_youth_seoul, is_primary=True
        )

        # 일반 유저 (조 권한 없음)
        cls.stranger = User.objects.create_user(username="stranger_r", password="x")
        UserDivisionTeam.objects.create(
            user=cls.stranger, division=cls.div_youth_seoul, is_primary=True
        )

        cls.superuser = User.objects.create_user(
            username="super_retreat",
            password="x",
            is_staff=True,
            is_superuser=True,
        )


class RetreatPermissionsTests(_BaseFixture):
    def test_leader_sees_only_own_group(self):
        groups = visible_retreat_groups_for(self.leader_seoul_1, self.event)
        codes = set(groups.values_list("id", flat=True))
        self.assertEqual(codes, {self.group_seoul_1.id})

    def test_leader_of_other_group_cannot_see_other(self):
        groups = visible_retreat_groups_for(self.leader_seoul_2, self.event)
        self.assertEqual(
            set(groups.values_list("id", flat=True)),
            {self.group_seoul_2.id},
        )

    def test_role_only_president_sees_no_groups_without_council(self):
        groups = visible_retreat_groups_for(self.staff_seoul, self.event)
        self.assertEqual(set(groups.values_list("id", flat=True)), set())

    def test_council_sees_all_groups(self):
        council = User.objects.create_user(username="council_all", password="x")
        RetreatCouncilMembership.objects.create(
            event=self.event,
            user=council,
            role=RetreatCouncilMembership.Role.CHAIRPERSON,
        )
        groups = visible_retreat_groups_for(council, self.event)
        self.assertEqual(
            set(groups.values_list("id", flat=True)),
            {self.group_seoul_1.id, self.group_seoul_2.id, self.group_incheon_1.id},
        )

    def test_pastor_sees_pastoral_division_groups_only(self):
        groups = visible_retreat_groups_for(self.pastor, self.event)
        self.assertEqual(
            set(groups.values_list("id", flat=True)),
            {self.group_seoul_1.id, self.group_seoul_2.id},
        )

    def test_pastor_without_assignment_sees_no_groups(self):
        unassigned = User.objects.create_user(username="pastor_none", password="x")
        unassigned.role_level = self.rl_pastor
        unassigned.save()
        groups = visible_retreat_groups_for(unassigned, self.event)
        self.assertEqual(set(groups.values_list("id", flat=True)), set())

    def test_staff_other_division_does_not_see_youth_groups(self):
        # 서울 대학부 부장: 청년부 그룹은 안 보여야 함 (division 다름)
        groups = visible_retreat_groups_for(self.staff_univ, self.event)
        self.assertEqual(set(groups.values_list("id", flat=True)), set())

    def test_superuser_sees_all_groups(self):
        groups = visible_retreat_groups_for(self.superuser, self.event)
        self.assertEqual(
            set(groups.values_list("id", flat=True)),
            {self.group_seoul_1.id, self.group_seoul_2.id, self.group_incheon_1.id},
        )

    def test_stranger_sees_nothing(self):
        groups = visible_retreat_groups_for(self.stranger, self.event)
        self.assertEqual(set(groups.values_list("id", flat=True)), set())

    def test_is_retreat_group_leader_true(self):
        self.assertTrue(
            is_retreat_group_leader(self.leader_seoul_1, self.group_seoul_1)
        )

    def test_is_retreat_group_leader_false_for_other(self):
        self.assertFalse(
            is_retreat_group_leader(self.leader_seoul_2, self.group_seoul_1)
        )

    def test_is_retreat_staff_false_for_role_only_president(self):
        self.assertFalse(is_retreat_staff(self.staff_seoul, self.event))

    def test_is_retreat_staff_true_for_council(self):
        council = User.objects.create_user(username="council_staff", password="x")
        RetreatCouncilMembership.objects.create(
            event=self.event,
            user=council,
            role=RetreatCouncilMembership.Role.CHAIRPERSON,
        )
        self.assertTrue(is_retreat_staff(council, self.event))

    def test_is_retreat_staff_false_for_stranger(self):
        self.assertFalse(is_retreat_staff(self.stranger, self.event))

    def test_role_only_president_cannot_access_retreat_tab(self):
        self.assertFalse(can_access_retreat_tab(self.staff_seoul))

    def test_dept_head_cannot_access_retreat_tab(self):
        self.assertFalse(can_access_retreat_tab(self.staff_univ))

    def test_pastor_can_access_retreat_tab(self):
        self.assertTrue(can_access_retreat_tab(self.pastor))

    def test_leader_can_access_retreat_tab(self):
        self.assertTrue(can_access_retreat_tab(self.leader_seoul_1))

    def test_pastor_cannot_view_retreat_all(self):
        self.assertFalse(can_view_retreat_all(self.pastor, self.event))

    def test_leader_cannot_view_retreat_all(self):
        self.assertFalse(can_view_retreat_all(self.leader_seoul_1, self.event))

    def test_leader_cannot_change_check_in(self):
        self.assertFalse(can_change_retreat_check_in(self.leader_seoul_1, self.event))

    def test_council_can_change_check_in(self):
        council = User.objects.create_user(username="council_checkin", password="x")
        RetreatCouncilMembership.objects.create(
            event=self.event,
            user=council,
            role=RetreatCouncilMembership.Role.CHAIRPERSON,
        )
        self.assertTrue(can_change_retreat_check_in(council, self.event))


class RetreatGroupAttendeesApiTests(_BaseFixture):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def test_other_leader_cannot_read_attendees_of_other_group(self):
        # 서울 2조 조장이 서울 1조 조원 목록 요청 → 403
        self.client.force_authenticate(self.leader_seoul_2)
        r = self.client.get(
            f"/api/v1/retreat/groups/{self.group_seoul_1.id}/attendees/"
        )
        self.assertEqual(r.status_code, 403)

    def test_leader_can_read_own_group_attendees(self):
        RetreatAttendee.objects.create(group=self.group_seoul_1, name="홍길동")
        self.client.force_authenticate(self.leader_seoul_1)
        r = self.client.get(
            f"/api/v1/retreat/groups/{self.group_seoul_1.id}/attendees/"
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()), 1)

    def test_leader_can_create_attendee_on_own_group(self):
        self.client.force_authenticate(self.leader_seoul_1)
        r = self.client.post(
            f"/api/v1/retreat/groups/{self.group_seoul_1.id}/attendees/",
            {"name": "신규조원", "phone": "010-0000-0000"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(
            RetreatAttendee.objects.filter(
                group=self.group_seoul_1, name="신규조원"
            ).exists()
        )

    def test_leader_cannot_create_attendee_on_other_group(self):
        self.client.force_authenticate(self.leader_seoul_2)
        r = self.client.post(
            f"/api/v1/retreat/groups/{self.group_seoul_1.id}/attendees/",
            {"name": "침입자"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_read_groups(self):
        self.client.force_authenticate(self.stranger)
        r = self.client.get(
            f"/api/v1/retreat/events/{self.event.id}/groups/"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_events_endpoint_shows_event_for_leader(self):
        self.client.force_authenticate(self.leader_seoul_1)
        r = self.client.get("/api/v1/retreat/events/")
        self.assertEqual(r.status_code, 200)
        ids = [e["id"] for e in r.json()]
        self.assertIn(self.event.id, ids)

    def test_events_endpoint_hides_event_for_stranger(self):
        self.client.force_authenticate(self.stranger)
        r = self.client.get("/api/v1/retreat/events/")
        self.assertEqual(r.status_code, 200)
        ids = [e["id"] for e in r.json()]
        self.assertNotIn(self.event.id, ids)

    def test_leader_can_patch_attendee_profile(self):
        att = RetreatAttendee.objects.create(
            group=self.group_seoul_1, name="홍길동", gender="male"
        )
        self.client.force_authenticate(self.leader_seoul_1)
        r = self.client.patch(
            f"/api/v1/retreat/attendees/{att.id}/",
            {"name": "홍길동수정", "phone": "010-1111-2222", "memo": "메모"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        att.refresh_from_db()
        self.assertEqual(att.name, "홍길동수정")
        self.assertEqual(att.phone, "010-1111-2222")
        self.assertEqual(att.memo, "메모")

    def test_leader_cannot_patch_check_in_status(self):
        att = RetreatAttendee.objects.create(group=self.group_seoul_1, name="상태대상")
        self.client.force_authenticate(self.leader_seoul_1)
        r = self.client.patch(
            f"/api/v1/retreat/attendees/{att.id}/",
            {"check_in_status": "checked_in"},
            format="json",
        )
        self.assertEqual(r.status_code, 403, r.content)
        att.refresh_from_db()
        self.assertEqual(att.check_in_status, "pending")

    def test_pastor_cannot_patch_attendee(self):
        att = RetreatAttendee.objects.create(group=self.group_seoul_1, name="목사읽기")
        self.client.force_authenticate(self.pastor)
        r = self.client.patch(
            f"/api/v1/retreat/attendees/{att.id}/",
            {"name": "변경시도"},
            format="json",
        )
        self.assertEqual(r.status_code, 403, r.content)


class RetreatAttendeeDeletePermissionTests(_BaseFixture):
    """조원 삭제 — 슈퍼유저·회장단·본인 조 조장/부조장."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.attendee = RetreatAttendee.objects.create(
            group=self.group_seoul_1, name="삭제대상"
        )
        self.url = f"/api/v1/retreat/attendees/{self.attendee.id}/"

    def test_staff_cannot_delete_attendee(self):
        # 서울 청년부 회장(staff)이지만 회장단(council)은 아님 → 삭제 불가
        self.client.force_authenticate(self.staff_seoul)
        r = self.client.delete(self.url)
        self.assertEqual(r.status_code, 403, r.content)
        self.assertTrue(RetreatAttendee.objects.filter(pk=self.attendee.id).exists())

    def test_leader_can_delete_attendee(self):
        self.client.force_authenticate(self.leader_seoul_1)
        r = self.client.delete(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json().get("deleted_pickup_count"), 0)
        self.assertFalse(RetreatAttendee.objects.filter(pk=self.attendee.id).exists())

    def test_council_can_delete_attendee(self):
        council = User.objects.create_user(username="council_seoul", password="x")
        UserDivisionTeam.objects.create(
            user=council, division=self.div_youth_seoul, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=self.event,
            user=council,
            role=RetreatCouncilMembership.Role.CHAIRPERSON,
        )
        self.client.force_authenticate(council)
        r = self.client.delete(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(RetreatAttendee.objects.filter(pk=self.attendee.id).exists())

    def test_superuser_can_delete_attendee(self):
        self.client.force_authenticate(self.superuser)
        r = self.client.delete(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(RetreatAttendee.objects.filter(pk=self.attendee.id).exists())
