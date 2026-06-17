"""조장·부조장 사용 가이드 페이지."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from retreat.models import RetreatEvent, RetreatGroup, RetreatGroupMembership
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class _LeaderGuideFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="guide_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="가이드 집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.leader = User.objects.create_user(username="guide_leader", password="x")
        RetreatGroupMembership.objects.create(
            user=cls.leader,
            group=cls.group,
            role=RetreatGroupMembership.Role.LEADER,
        )
        cls.council = User.objects.create_user(username="guide_council", password="x")
        rl, _ = RoleLevel.objects.get_or_create(
            code="president",
            defaults={"name": "회장", "level": 80, "sort_order": 20},
        )
        cls.council.role_level = rl
        cls.council.save()
        from retreat.models import RetreatCouncilMembership

        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council,
            role=RetreatCouncilMembership.Role.CHAIRPERSON,
        )
        cls.stranger = User.objects.create_user(username="guide_stranger", password="x")
        UserDivisionTeam.objects.create(
            user=cls.stranger, division=cls.div, is_primary=True
        )


class RetreatLeaderGuidePageTests(_LeaderGuideFixture):
    def test_leader_can_view_guide(self):
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_leader_guide"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "조장 부조장 수련회 앱 이용 가이드")
        self.assertContains(r, reverse("retreat_dashboard", args=[self.event.id]))
        self.assertContains(r, "retreat/guides/01.png")

    def test_council_without_membership_forbidden(self):
        self.client.force_login(self.council)
        r = self.client.get(reverse("retreat_leader_guide"))
        self.assertEqual(r.status_code, 403)

    def test_stranger_forbidden(self):
        self.client.force_login(self.stranger)
        r = self.client.get(reverse("retreat_leader_guide"))
        self.assertEqual(r.status_code, 403)

    def test_manage_groups_shows_guide_link_for_leader(self):
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse("retreat_group_manage_list", args=[self.event.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, reverse("retreat_leader_guide"))
        self.assertContains(r, "사용 가이드")

    def test_manage_groups_hides_guide_link_for_council_only(self):
        self.client.force_login(self.council)
        r = self.client.get(
            reverse("retreat_group_manage_list", args=[self.event.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "사용 가이드")
