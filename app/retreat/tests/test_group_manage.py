"""조 추가·운영진 권한·온보딩 승인 연동 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
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
    RetreatGroupScope,
)
from retreat.services.lodging import assert_room_can_accept, rooms_for_group
from users.models import Division, Region, RoleLevel, UserDivisionTeam, UserProfile
from users.permissions import can_add_retreat_group, can_manage_retreat_group_leaders

User = get_user_model()


class _GroupManageFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="gm_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="조관리 집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )

        cls.rl_pastor, _ = RoleLevel.objects.get_or_create(
            code="pastor",
            defaults={"name": "목사", "level": 80, "sort_order": 10},
        )
        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president",
            defaults={"name": "회장", "level": 80, "sort_order": 20},
        )

        cls.council_user = User.objects.create_user(username="gm_council", password="x")
        cls.council_user.role_level = cls.rl_president
        cls.council_user.save()
        from retreat.models import RetreatCouncilMembership

        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council_user,
            role=RetreatCouncilMembership.Role.CHAIRPERSON,
        )

        cls.pastor = User.objects.create_user(username="gm_pastor", password="x")
        cls.pastor.role_level = cls.rl_pastor
        cls.pastor.save()
        UserDivisionTeam.objects.create(
            user=cls.pastor, division=cls.div, is_primary=True
        )

        cls.leader = User.objects.create_user(username="gm_leader", password="x")
        RetreatGroupMembership.objects.create(
            user=cls.leader, group=cls.group, role=RetreatGroupMembership.Role.LEADER
        )


class GroupCreatePermissionTests(_GroupManageFixture):
    def test_council_can_add_group(self):
        self.assertTrue(can_add_retreat_group(self.council_user, self.event))

    def test_pastor_cannot_add_group(self):
        self.assertFalse(can_add_retreat_group(self.pastor, self.event))

    def test_leader_can_manage_leaders_on_own_group(self):
        self.assertTrue(
            can_manage_retreat_group_leaders(self.leader, self.group)
        )

    def test_pastor_cannot_manage_leaders(self):
        self.assertFalse(can_manage_retreat_group_leaders(self.pastor, self.group))


class GroupCreateApiTests(_GroupManageFixture):
    def setUp(self):
        self.client = APIClient()

    def _url(self):
        return reverse("api_retreat_event_groups", args=[self.event.id])

    def test_council_can_create_group_with_leader(self):
        self.client.force_authenticate(self.council_user)
        member = User.objects.create_user(username="gm_new_leader", password="x")
        r = self.client.post(
            self._url(),
            {
                "region": self.seoul.id,
                "division": self.div.id,
                "name": "99조",
                "order": 99,
                "leaders": [{"user_id": member.id, "role": "leader"}],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        group = RetreatGroup.objects.get(event=self.event, name="99조")
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=group, user=member, role="leader"
            ).exists()
        )

    def test_pastor_cannot_create_group(self):
        self.client.force_authenticate(self.pastor)
        r = self.client.post(
            self._url(),
            {
                "region": self.seoul.id,
                "division": self.div.id,
                "name": "X조",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_create_group_records_created_by(self):
        """조 추가 시 생성자(created_by)가 기록된다."""
        self.client.force_authenticate(self.council_user)
        r = self.client.post(
            self._url(),
            {
                "region": self.seoul.id,
                "division": self.div.id,
                "name": "77조",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        group = RetreatGroup.objects.get(event=self.event, name="77조")
        self.assertEqual(group.created_by_id, self.council_user.id)

    def test_council_can_bulk_create_groups_with_leaders(self):
        self.client.force_authenticate(self.council_user)
        leader_a = User.objects.create_user(username="gm_bulk_a", password="x")
        leader_b = User.objects.create_user(username="gm_bulk_b", password="x")
        r = self.client.post(
            self._url(),
            {
                "groups": [
                    {
                        "region": self.seoul.id,
                        "division": self.div.id,
                        "name": "88조",
                        "order": 88,
                        "leaders": [{"user_id": leader_a.id, "role": "leader"}],
                    },
                    {
                        "region": self.seoul.id,
                        "division": self.div.id,
                        "name": "89조",
                        "order": 89,
                        "leaders": [{"user_id": leader_b.id, "role": "vice_leader"}],
                    },
                ]
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.json()), 2)
        g88 = RetreatGroup.objects.get(event=self.event, name="88조")
        g89 = RetreatGroup.objects.get(event=self.event, name="89조")
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=g88, user=leader_a, role="leader"
            ).exists()
        )
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=g89, user=leader_b, role="vice_leader"
            ).exists()
        )

    def test_bulk_create_rolls_back_on_duplicate_name_in_batch(self):
        self.client.force_authenticate(self.council_user)
        before = RetreatGroup.objects.filter(event=self.event).count()
        r = self.client.post(
            self._url(),
            {
                "groups": [
                    {
                        "region": self.seoul.id,
                        "division": self.div.id,
                        "name": "중복조",
                    },
                    {
                        "region": self.seoul.id,
                        "division": self.div.id,
                        "name": "중복조",
                    },
                ]
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(RetreatGroup.objects.filter(event=self.event).count(), before)

    def test_council_can_create_group_with_extra_scopes(self):
        incheon, _ = Region.objects.get_or_create(
            code="incheon", defaults={"name": "인천", "sort_order": 20}
        )
        incheon_div = Division.objects.create(
            region=incheon, code="gm_incheon_youth", name="청년부"
        )
        self.client.force_authenticate(self.council_user)
        r = self.client.post(
            self._url(),
            {
                "region": self.seoul.id,
                "division": self.div.id,
                "name": "20조",
                "order": 20,
                "scopes": [
                    {"region": incheon.id, "division": incheon_div.id},
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        group = RetreatGroup.objects.get(event=self.event, name="20조")
        self.assertEqual(group.extra_scopes.count(), 1)
        scope = group.extra_scopes.get()
        self.assertEqual(scope.region_id, incheon.id)
        self.assertEqual(scope.division_id, incheon_div.id)
        payload = r.json()
        self.assertEqual(len(payload.get("extra_scopes") or []), 1)

    def test_create_rejects_duplicate_primary_in_scopes(self):
        self.client.force_authenticate(self.council_user)
        r = self.client.post(
            self._url(),
            {
                "region": self.seoul.id,
                "division": self.div.id,
                "name": "dup_scope",
                "scopes": [
                    {"region": self.seoul.id, "division": self.div.id},
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)


class GroupDetailApiTests(_GroupManageFixture):
    def setUp(self):
        self.client = APIClient()

    def _url(self, group_id=None):
        return reverse(
            "api_retreat_group_detail",
            args=[group_id or self.group.id],
        )

    def test_council_can_patch_group_name_primary_and_scopes(self):
        incheon, _ = Region.objects.get_or_create(
            code="incheon", defaults={"name": "인천", "sort_order": 20}
        )
        incheon_div = Division.objects.create(
            region=incheon, code="gm_patch_youth", name="청년부"
        )
        self.client.force_authenticate(self.council_user)
        r = self.client.patch(
            self._url(),
            {
                "name": "1조-수정",
                "region": self.seoul.id,
                "division": self.div.id,
                "order": 5,
                "scopes": [
                    {"region": incheon.id, "division": incheon_div.id},
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, "1조-수정")
        self.assertEqual(self.group.order, 5)
        self.assertEqual(self.group.extra_scopes.count(), 1)
        scope = self.group.extra_scopes.get()
        self.assertEqual(scope.region_id, incheon.id)
        self.assertEqual(scope.division_id, incheon_div.id)
        payload = r.json()
        self.assertEqual(payload["name"], "1조-수정")
        self.assertEqual(len(payload.get("extra_scopes") or []), 1)

    def test_pastor_cannot_patch_group(self):
        self.client.force_authenticate(self.pastor)
        r = self.client.patch(
            self._url(),
            {"name": "변경불가"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_patch_rejects_duplicate_name_excluding_self(self):
        RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
            order=2,
        )
        self.client.force_authenticate(self.council_user)
        r = self.client.patch(
            self._url(),
            {"name": "2조"},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)


class GroupExtraScopeBehaviorTests(_GroupManageFixture):
    def test_rooms_for_group_includes_extra_scope_rooms(self):
        incheon, _ = Region.objects.get_or_create(
            code="incheon", defaults={"name": "인천", "sort_order": 20}
        )
        incheon_div = Division.objects.create(
            region=incheon, code="gm_scope_youth", name="청년부"
        )
        group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="scope_group",
            order=30,
        )
        RetreatGroupScope.objects.create(
            group=group, region=incheon, division=incheon_div
        )
        lodging_seoul = Lodging.objects.create(event=self.event, name="서울숙소")
        lodging_incheon = Lodging.objects.create(event=self.event, name="인천숙소")
        room_seoul = LodgingRoom.objects.create(
            lodging=lodging_seoul,
            number="101",
            region=self.seoul,
            division=self.div,
        )
        room_incheon = LodgingRoom.objects.create(
            lodging=lodging_incheon,
            number="201",
            region=incheon,
            division=incheon_div,
        )
        room_ids = set(rooms_for_group(group).values_list("id", flat=True))
        self.assertEqual(room_ids, {room_seoul.id, room_incheon.id})

    def test_assert_room_can_accept_allows_extra_scope_room(self):
        incheon, _ = Region.objects.get_or_create(
            code="incheon", defaults={"name": "인천", "sort_order": 20}
        )
        incheon_div = Division.objects.create(
            region=incheon, code="gm_scope_youth2", name="청년부"
        )
        group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="scope_group2",
            order=31,
        )
        RetreatGroupScope.objects.create(
            group=group, region=incheon, division=incheon_div
        )
        lodging = Lodging.objects.create(event=self.event, name="인천숙소2")
        room = LodgingRoom.objects.create(
            lodging=lodging,
            number="301",
            region=incheon,
            division=incheon_div,
        )
        attendee = RetreatAttendee.objects.create(group=group, name="테스트")
        assert_room_can_accept(room, attendee)


class AttendeeEditPermissionTests(_GroupManageFixture):
    def setUp(self):
        self.client = APIClient()
        self.attendee = RetreatAttendee.objects.create(
            group=self.group, name="편집대상", gender="male"
        )
        self.url = reverse(
            "api_retreat_attendee_detail",
            args=[self.attendee.id],
        )

    def test_leader_can_patch_profile_fields(self):
        self.client.force_authenticate(self.leader)
        r = self.client.patch(
            self.url,
            {
                "name": "이름변경",
                "phone": "010-9999-8888",
                "member_role": "member",
                "memo": "조장메모",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.name, "이름변경")
        self.assertEqual(self.attendee.phone, "010-9999-8888")
        self.assertEqual(self.attendee.memo, "조장메모")

    def test_phone_digits_only_normalized_on_save(self):
        self.client.force_authenticate(self.leader)
        r = self.client.patch(
            self.url,
            {"phone": "01044442222"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.phone, "010-4444-2222")
        self.assertEqual(r.data["phone"], "010-4444-2222")

    def test_leader_cannot_patch_check_in_status(self):
        self.client.force_authenticate(self.leader)
        r = self.client.patch(
            self.url,
            {"check_in_status": "checked_in"},
            format="json",
        )
        self.assertEqual(r.status_code, 403, r.content)

    def test_leader_can_delete_attendee(self):
        victim = RetreatAttendee.objects.create(group=self.group, name="삭제대상")
        url = reverse("api_retreat_attendee_detail", args=[victim.id])
        self.client.force_authenticate(self.leader)
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 204, r.content)
        self.assertFalse(RetreatAttendee.objects.filter(pk=victim.id).exists())

    def test_pastor_cannot_patch_attendee(self):
        self.client.force_authenticate(self.pastor)
        r = self.client.patch(self.url, {"name": "목사변경"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    def test_pastor_cannot_delete_attendee(self):
        self.client.force_authenticate(self.pastor)
        r = self.client.delete(self.url)
        self.assertEqual(r.status_code, 403, r.content)


class AttendeeExpectedTimeValidationTests(_GroupManageFixture):
    """입실/퇴실 예상 시각: 퇴실은 입실보다 무조건 뒤여야 한다."""

    def setUp(self):
        self.client = APIClient()
        self.attendee = RetreatAttendee.objects.create(
            group=self.group, name="시간검증", gender="male"
        )
        self.url = reverse("api_retreat_attendee_detail", args=[self.attendee.id])
        self.client.force_authenticate(self.council_user)

    def test_check_out_before_check_in_rejected(self):
        r = self.client.patch(
            self.url,
            {
                "expected_check_in_at": "2026-01-01T01:10:00+09:00",
                "expected_check_out_at": "2026-01-01T01:09:00+09:00",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("expected_check_out_at", r.json())

    def test_check_out_equal_check_in_rejected(self):
        r = self.client.patch(
            self.url,
            {
                "expected_check_in_at": "2026-01-01T01:10:00+09:00",
                "expected_check_out_at": "2026-01-01T01:10:00+09:00",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("expected_check_out_at", r.json())

    def test_check_out_after_check_in_allowed(self):
        r = self.client.patch(
            self.url,
            {
                "expected_check_in_at": "2026-01-01T01:10:00+09:00",
                "expected_check_out_at": "2026-01-01T01:11:00+09:00",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.attendee.refresh_from_db()
        self.assertIsNotNone(self.attendee.expected_check_out_at)

    def test_partial_update_compares_with_existing_check_in(self):
        # 먼저 입실 시각을 정해두고, 그보다 이른 퇴실만 단독 PATCH 하면 거부.
        self.attendee.expected_check_in_at = "2026-01-01T01:10:00+09:00"
        self.attendee.save(update_fields=["expected_check_in_at"])
        r = self.client.patch(
            self.url,
            {"expected_check_out_at": "2026-01-01T01:05:00+09:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("expected_check_out_at", r.json())

    def test_auto_checked_out_cannot_patch_expected_timestamps(self):
        from datetime import timedelta

        from django.utils import timezone

        now = timezone.now()
        self.attendee.check_in_status = RetreatAttendee.CheckInStatus.CHECKED_OUT
        self.attendee.expected_check_in_at = now - timedelta(hours=2)
        self.attendee.expected_check_out_at = now - timedelta(hours=1)
        self.attendee.checked_out_at = now
        self.attendee.save(
            update_fields=[
                "check_in_status",
                "expected_check_in_at",
                "expected_check_out_at",
                "checked_out_at",
            ]
        )
        r = self.client.patch(
            self.url,
            {"expected_check_in_at": "2026-07-01T10:00:00+09:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("expected_check_in_at", r.json())

    def test_manual_early_checkout_can_still_patch_expected_timestamps(self):
        from datetime import timedelta

        from django.utils import timezone

        now = timezone.now()
        self.attendee.check_in_status = RetreatAttendee.CheckInStatus.CHECKED_OUT
        self.attendee.expected_check_out_at = now + timedelta(hours=2)
        self.attendee.save(
            update_fields=["check_in_status", "expected_check_out_at"]
        )
        r = self.client.patch(
            self.url,
            {
                "expected_check_in_at": "2026-07-01T10:00:00+09:00",
                "expected_check_out_at": "2026-07-01T18:00:00+09:00",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.attendee.refresh_from_db()
        self.assertIsNotNone(self.attendee.expected_check_in_at)


class AttendeeCheckInStatusEditTests(_GroupManageFixture):
    """회장단은 입실 상태를 자유롭게(되돌리기 포함) 수정할 수 있어야 한다."""

    def setUp(self):
        self.client = APIClient()
        self.attendee = RetreatAttendee.objects.create(
            group=self.group,
            name="상태수정대상",
            gender="male",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        self.url = reverse("api_retreat_attendee_detail", args=[self.attendee.id])

    def test_council_can_revert_checked_out_to_checked_in(self):
        self.client.force_authenticate(self.council_user)
        r = self.client.patch(
            self.url, {"check_in_status": "checked_in"}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.check_in_status, "checked_in")

    def test_council_can_revert_to_pending(self):
        self.client.force_authenticate(self.council_user)
        r = self.client.patch(
            self.url, {"check_in_status": "pending"}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.check_in_status, "pending")

    def test_leader_cannot_change_check_in_status(self):
        self.client.force_authenticate(self.leader)
        r = self.client.patch(
            self.url, {"check_in_status": "checked_in"}, format="json"
        )
        self.assertEqual(r.status_code, 403, r.content)


class GroupMembershipWritePermissionTests(_GroupManageFixture):
    def setUp(self):
        self.client = APIClient()

    def test_pastor_cannot_add_membership(self):
        self.client.force_authenticate(self.pastor)
        target = User.objects.create_user(username="gm_target", password="x")
        url = reverse("api_retreat_group_memberships", args=[self.group.id])
        r = self.client.post(
            url, {"user_id": target.id, "role": "leader"}, format="json"
        )
        self.assertEqual(r.status_code, 403)


class OnboardingRetreatAssignTests(_GroupManageFixture):
    def test_participant_creates_attendee_only(self):
        from retreat.services.onboarding import apply_retreat_membership_on_approval

        applicant = User.objects.create_user(username="gm_applicant", password="x")
        profile = UserProfile.objects.create(
            user=applicant,
            requested_retreat_participation=True,
            requested_retreat_event=self.event,
            requested_retreat_role="participant",
        )
        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group.id),
            retreat_role="participant",
            changed_by=self.council_user,
        )
        self.assertFalse(
            RetreatGroupMembership.objects.filter(
                user=applicant, group=self.group
            ).exists()
        )
        self.assertTrue(
            RetreatAttendee.objects.filter(group=self.group, name=applicant.username).exists()
        )

    def test_leader_creates_membership_and_attendee(self):
        from retreat.services.onboarding import apply_retreat_membership_on_approval

        applicant = User.objects.create_user(username="gm_leader_app", password="x")
        profile = UserProfile.objects.create(
            user=applicant,
            requested_retreat_participation=True,
            requested_retreat_event=self.event,
            requested_retreat_role="leader",
        )
        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group.id),
            retreat_role="leader",
            changed_by=self.council_user,
        )
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                user=applicant, group=self.group, role="leader"
            ).exists()
        )
        self.assertTrue(
            RetreatAttendee.objects.filter(
                group=self.group, name=applicant.username
            ).exists()
        )


class AttendeeCreateCreatedByTests(_GroupManageFixture):
    def setUp(self):
        self.client = APIClient()

    def test_create_attendee_records_created_by(self):
        """조원 추가 시 생성자(created_by)가 기록된다."""
        self.client.force_authenticate(self.leader)
        r = self.client.post(
            reverse("api_retreat_group_attendees", args=[self.group.id]),
            {"name": "기록조원"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        attendee = RetreatAttendee.objects.get(pk=r.json()["id"])
        self.assertEqual(attendee.created_by_id, self.leader.id)
