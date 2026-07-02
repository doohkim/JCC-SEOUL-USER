"""조 운영진(조장/부조장) CRUD API 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from retreat.models import (
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
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


class GroupMembershipApiTests(APITestCase, _Fixture):
    @classmethod
    def setUpTestData(cls):
        cls.setup_fixture()

    def setUp(self):
        self.client = APIClient()

    def _list_url(self):
        return reverse("api_retreat_group_memberships", args=[self.group.id])

    def _detail_url(self, membership_id):
        return reverse(
            "api_retreat_group_membership_detail", args=[membership_id]
        )

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
        m = RetreatGroupMembership.objects.get(
            group=self.group, user=self.leader
        )
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
        m = RetreatGroupMembership.objects.get(
            group=self.group, user=self.leader
        )
        r = self.client.delete(self._detail_url(m.id))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(
            RetreatGroupMembership.objects.filter(pk=m.id).exists()
        )

    def test_outsider_cannot_delete(self):
        self.client.force_authenticate(self.outsider)
        m = RetreatGroupMembership.objects.get(
            group=self.group, user=self.leader
        )
        r = self.client.delete(self._detail_url(m.id))
        self.assertIn(r.status_code, (403, 404))
