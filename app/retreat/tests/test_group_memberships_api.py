"""조 운영진(조장/부조장) CRUD API 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from retreat.models import (
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
from users.mixins import ensure_user_profile
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class _Fixture:
    @classmethod
    def setup_fixture(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="gm_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="조 운영진 테스트",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president",
            defaults={"name": "회장", "level": 80, "sort_order": 20},
        )

        cls.council = User.objects.create_user(username="gm_council", password="x")
        cls.council.role_level = cls.rl_president
        cls.council.save()
        UserDivisionTeam.objects.create(
            user=cls.council, division=cls.div, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

        cls.leader = User.objects.create_user(username="gm_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.outsider = User.objects.create_user(username="gm_outsider", password="x")

        cls.new_member = User.objects.create_user(
            username="gm_new_member", password="x"
        )
        profile = ensure_user_profile(cls.new_member)
        profile.real_name = "신규성도"
        profile.gender = profile.Gender.FEMALE
        profile.phone = "010-9999-8888"
        profile.save(update_fields=["real_name", "gender", "phone", "updated_at"])


class GroupMembershipApiTests(APITestCase, _Fixture):
    @classmethod
    def setUpTestData(cls):
        cls.setup_fixture()

    def setUp(self):
        self.client = APIClient()

    def _list_url(self):
        return reverse("api_retreat_group_memberships", args=[self.group.id])

    def _detail_url(self, membership_id):
        return reverse("api_retreat_group_membership_detail", args=[membership_id])

    def test_council_can_add_leader(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(
            self._list_url(),
            {"username": self.new_member.username, "role": "vice_leader"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=self.group,
                user=self.new_member,
                role="vice_leader",
            ).exists()
        )

    def test_leader_can_add_to_own_group(self):
        self.client.force_authenticate(self.leader)
        r = self.client.post(
            self._list_url(),
            {"username": self.new_member.username},
            format="json",
        )
        self.assertEqual(r.status_code, 201)

    def test_outsider_cannot_add(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.post(
            self._list_url(),
            {"username": self.new_member.username},
            format="json",
        )
        self.assertIn(r.status_code, (403, 404))

    def test_unknown_username_returns_400(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(
            self._list_url(),
            {"username": "no_such_user_xyz"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_role_validated(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(
            self._list_url(),
            {"username": self.new_member.username, "role": "boss"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_list_returns_existing(self):
        self.client.force_authenticate(self.council)
        r = self.client.get(self._list_url())
        self.assertEqual(r.status_code, 200)
        usernames = [m["username"] for m in r.json()]
        self.assertIn(self.leader.username, usernames)

    def test_patch_role(self):
        self.client.force_authenticate(self.council)
        m = RetreatGroupMembership.objects.get(group=self.group, user=self.leader)
        r = self.client.patch(
            self._detail_url(m.id),
            {"role": "vice_leader"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        m.refresh_from_db()
        self.assertEqual(m.role, "vice_leader")

    def test_delete(self):
        self.client.force_authenticate(self.council)
        m = RetreatGroupMembership.objects.get(group=self.group, user=self.leader)
        r = self.client.delete(self._detail_url(m.id))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(RetreatGroupMembership.objects.filter(pk=m.id).exists())

    def test_add_leader_syncs_attendee_gender_from_profile(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(
            self._list_url(),
            {"username": self.new_member.username, "role": "leader"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        attendee = RetreatAttendee.objects.get(group=self.group, user=self.new_member)
        self.assertEqual(attendee.name, "신규성도")
        self.assertEqual(attendee.gender, "female")
        self.assertEqual(attendee.phone, "010-9999-8888")

    def test_cross_group_leader_keeps_home_and_blocks_duplicate_attendee(self):
        group2 = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        self.client.force_authenticate(self.council)
        r1 = self.client.post(
            self._list_url(),
            {"username": self.new_member.username, "role": "leader"},
            format="json",
        )
        self.assertEqual(r1.status_code, 201, r1.content)
        self.assertEqual(
            RetreatAttendee.objects.filter(
                user=self.new_member, group__event=self.event
            ).count(),
            1,
        )

        url2 = reverse("api_retreat_group_memberships", args=[group2.id])
        r2 = self.client.post(
            url2,
            {"username": self.new_member.username, "role": "leader"},
            format="json",
        )
        self.assertEqual(r2.status_code, 201, r2.content)
        body = r2.json()
        self.assertTrue(body.get("kept_home_group"))
        self.assertTrue(body.get("is_cross_group_leader"))
        self.assertEqual(body.get("home_group_id"), self.group.id)
        self.assertFalse(
            RetreatAttendee.objects.filter(group=group2, user=self.new_member).exists()
        )
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=group2, user=self.new_member, role="leader"
            ).exists()
        )

        attendee_url = reverse("api_retreat_group_attendees", args=[group2.id])
        r3 = self.client.post(
            attendee_url,
            {
                "name": "신규성도",
                "gender": "female",
                "user": self.new_member.id,
                "member_role": "leader",
            },
            format="json",
        )
        self.assertEqual(r3.status_code, 400, r3.content)
        self.assertIn("user", r3.json())

    def test_member_appointed_other_group_leader_moves_home(self):
        group2 = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="이동대상조",
        )
        member = User.objects.create_user(username="gm_move_member", password="x")
        profile = ensure_user_profile(member)
        profile.real_name = "이동성도"
        profile.save(update_fields=["real_name", "updated_at"])
        RetreatAttendee.objects.create(
            group=self.group,
            user=member,
            name="이동성도",
            member_role=RetreatAttendee.MemberRole.MEMBER,
            gender=RetreatAttendee.Gender.FEMALE,
        )
        self.client.force_authenticate(self.council)
        r = self.client.post(
            reverse("api_retreat_group_memberships", args=[group2.id]),
            {"username": member.username, "role": "leader"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertTrue(body.get("moved_home_group"))
        self.assertEqual(body.get("home_group_id"), group2.id)
        self.assertFalse(
            RetreatAttendee.objects.filter(group=self.group, user=member).exists()
        )
        self.assertTrue(
            RetreatAttendee.objects.filter(
                group=group2,
                user=member,
                member_role=RetreatAttendee.MemberRole.LEADER,
            ).exists()
        )

    def test_home_role_upgrade_blocked_when_other_group_leader(self):
        group2 = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="겸직조",
        )
        target = User.objects.create_user(username="gm_block_promo", password="x")
        profile = ensure_user_profile(target)
        profile.real_name = "승격차단"
        profile.save(update_fields=["real_name", "updated_at"])
        self.client.force_authenticate(self.council)
        # 소속: group2 조장
        self.client.post(
            reverse("api_retreat_group_memberships", args=[group2.id]),
            {"username": target.username, "role": "leader"},
            format="json",
        )
        # 겸직: 1조 운영진 (소속 유지)
        self.client.post(
            self._list_url(),
            {"username": target.username, "role": "leader"},
            format="json",
        )
        home = RetreatAttendee.objects.get(group=group2, user=target)
        home.member_role = RetreatAttendee.MemberRole.MEMBER
        home.save(update_fields=["member_role", "updated_at"])
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=self.group, user=target
            ).exists()
        )
        r = self.client.patch(
            reverse("api_retreat_attendee_detail", args=[home.id]),
            {"member_role": "leader"},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("member_role", r.json())

    def test_delete_home_attendee_cascades_all_memberships(self):
        group2 = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="3조",
        )
        self.client.force_authenticate(self.council)
        self.client.post(
            self._list_url(),
            {"username": self.new_member.username, "role": "leader"},
            format="json",
        )
        self.client.post(
            reverse("api_retreat_group_memberships", args=[group2.id]),
            {"username": self.new_member.username, "role": "vice_leader"},
            format="json",
        )
        attendee = RetreatAttendee.objects.get(group=self.group, user=self.new_member)
        r = self.client.delete(
            reverse("api_retreat_attendee_detail", args=[attendee.id])
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(
            RetreatGroupMembership.objects.filter(
                user=self.new_member, group__event=self.event
            ).exists()
        )

    def test_outsider_cannot_delete(self):
        self.client.force_authenticate(self.outsider)
        m = RetreatGroupMembership.objects.get(group=self.group, user=self.leader)
        r = self.client.delete(self._detail_url(m.id))
        self.assertIn(r.status_code, (403, 404))
