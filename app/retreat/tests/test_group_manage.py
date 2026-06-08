"""조 추가·운영진 권한·온보딩 승인 연동 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
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
            name="조관리 행사",
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
