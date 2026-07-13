"""탈퇴 계정 조원·픽업 숨김 테스트."""

from __future__ import annotations

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
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
from users.models import Division, Region, UserDivisionTeam
from users.services.account_lifecycle import retire_user

User = get_user_model()


def _train_time(hour: int, minute: int = 0):
    return timezone.make_aware(datetime(2026, 8, 1, hour, minute))


class AccountRetiredVisibilityFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="retired_vis_div", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="탈퇴 가시성 테스트",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )

        cls.superuser = User.objects.create_superuser(
            username="retired_vis_super", password="x"
        )
        cls.event_admin = User.objects.create_user(
            username="retired_vis_admin", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.event_admin, division=cls.div, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.event_admin,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

        cls.target = User.objects.create_user(username="retired_vis_target", password="x")
        cls.attendee = RetreatAttendee.objects.create(
            group=cls.group,
            user=cls.target,
            name="김탈퇴",
            phone="010-1234-5678",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        cls.pickup = RetreatPickup.objects.create(
            event=cls.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=cls.group,
            name="김탈퇴",
            region=cls.seoul,
            division=cls.div,
            train_time=_train_time(9),
            boarding_place="서울역",
            contact="010-1234-5678",
        )
        cls.active_attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="활성조원",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.target,
            role=RetreatCouncilMembership.Role.DIVISION_OBSERVER,
            division=cls.div,
        )
        RetreatGroupMembership.objects.create(
            group=cls.group,
            user=cls.target,
            role=RetreatGroupMembership.Role.LEADER,
        )
        cls.active_staff = User.objects.create_user(
            username="retired_vis_active_staff", password="x"
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.active_staff,
            role=RetreatCouncilMembership.Role.EVENT_OBSERVER,
        )

    def setUp(self):
        self.api = APIClient()
        self.web = Client()

    def _retire_target(self):
        retire_user(self.target)
        self.attendee.refresh_from_db()
        self.pickup.refresh_from_db()

    def test_retire_marks_attendee_and_pickup(self):
        self._retire_target()
        self.assertIsNotNone(self.attendee.account_retired_at)
        self.assertIsNotNone(self.pickup.account_retired_at)
        self.assertTrue(RetreatAttendee.objects.filter(pk=self.attendee.pk).exists())
        self.assertTrue(RetreatPickup.objects.filter(pk=self.pickup.pk).exists())

    def test_superuser_cannot_see_retired_attendee_and_pickup(self):
        self._retire_target()
        self.api.force_authenticate(self.superuser)
        att_r = self.api.get(
            reverse("api_retreat_group_attendees", args=[self.group.id])
        )
        self.assertEqual(att_r.status_code, 200, att_r.content)
        names = {row["name"] for row in att_r.data}
        self.assertNotIn("김탈퇴", names)
        self.assertIn("활성조원", names)

        pickup_r = self.api.get(
            reverse("api_retreat_event_pickups", args=[self.event.id]),
            {"direction": RetreatPickup.Direction.ARRIVAL},
        )
        self.assertEqual(pickup_r.status_code, 200, pickup_r.content)
        pickup_names = {row["name"] for row in pickup_r.data}
        self.assertNotIn("김탈퇴", pickup_names)

    def test_event_admin_cannot_see_retired_rows(self):
        self._retire_target()
        self.api.force_authenticate(self.event_admin)
        att_r = self.api.get(
            reverse("api_retreat_group_attendees", args=[self.group.id])
        )
        self.assertEqual(att_r.status_code, 200, att_r.content)
        names = {row["name"] for row in att_r.data}
        self.assertNotIn("김탈퇴", names)
        self.assertIn("활성조원", names)

        pickup_r = self.api.get(
            reverse("api_retreat_event_pickups", args=[self.event.id]),
            {"direction": RetreatPickup.Direction.ARRIVAL},
        )
        self.assertEqual(pickup_r.status_code, 200, pickup_r.content)
        pickup_names = {row["name"] for row in pickup_r.data}
        self.assertNotIn("김탈퇴", pickup_names)

    def test_event_admin_gets_404_for_retired_attendee_detail(self):
        self._retire_target()
        self.api.force_authenticate(self.event_admin)
        r = self.api.get(reverse("api_retreat_attendee_detail", args=[self.attendee.id]))
        self.assertEqual(r.status_code, 404, r.content)

    def test_event_admin_gets_404_for_retired_pickup_patch(self):
        self._retire_target()
        self.api.force_authenticate(self.event_admin)
        r = self.api.patch(
            reverse("api_retreat_pickup_detail", args=[self.pickup.id]),
            {"note": "변경"},
            format="json",
        )
        self.assertEqual(r.status_code, 404, r.content)

    def test_superuser_pickup_page_hides_retired_pickup(self):
        self._retire_target()
        self.web.force_login(self.superuser)
        r = self.web.get(
            reverse("retreat_pickup", args=[self.event.id])
            + "?tab=all&date="
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotContains(r, "탈퇴 계정")
        self.assertNotContains(r, "김탈퇴")

    def test_event_admin_pickup_page_hides_retired_pickup(self):
        self._retire_target()
        self.web.force_login(self.event_admin)
        r = self.web.get(
            reverse("retreat_pickup", args=[self.event.id])
            + "?tab=all&date="
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotContains(r, "김탈퇴")

    def test_mark_orphan_retired_pickups_command(self):
        orphan = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=9,
            group=self.group,
            name="고아픽업",
            region=self.seoul,
            division=self.div,
            train_time=_train_time(12),
            boarding_place="역",
            contact="010-9999-8888",
        )
        from django.core.management import call_command

        call_command("mark_orphan_retired_pickups", event_id=self.event.id)
        orphan.refresh_from_db()
        self.assertIsNotNone(orphan.account_retired_at)

        self.api.force_authenticate(self.event_admin)
        pickup_r = self.api.get(
            reverse("api_retreat_event_pickups", args=[self.event.id]),
            {"direction": RetreatPickup.Direction.ARRIVAL},
        )
        self.assertEqual(pickup_r.status_code, 200, pickup_r.content)
        self.assertNotIn("고아픽업", {row["name"] for row in pickup_r.data})

    def test_superuser_cannot_see_retired_staff_in_council_roster(self):
        self._retire_target()
        self.api.force_authenticate(self.superuser)
        r = self.api.get(reverse("api_retreat_event_council", args=[self.event.id]))
        self.assertEqual(r.status_code, 200, r.content)
        user_ids = {row["user"] for row in r.data}
        self.assertNotIn(self.target.id, user_ids)
        self.assertIn(self.active_staff.id, user_ids)

    def test_event_admin_cannot_see_retired_staff_in_council_roster(self):
        self._retire_target()
        self.api.force_authenticate(self.event_admin)
        r = self.api.get(reverse("api_retreat_event_council", args=[self.event.id]))
        self.assertEqual(r.status_code, 200, r.content)
        user_ids = {row["user"] for row in r.data}
        self.assertNotIn(self.target.id, user_ids)
        self.assertIn(self.active_staff.id, user_ids)

    def test_event_admin_cannot_see_retired_group_leader_in_groups_api(self):
        self._retire_target()
        self.api.force_authenticate(self.event_admin)
        r = self.api.get(reverse("api_retreat_event_groups", args=[self.event.id]))
        self.assertEqual(r.status_code, 200, r.content)
        group = next(item for item in r.data if item["id"] == self.group.id)
        member_user_ids = {m["user"] for m in group["memberships"]}
        self.assertNotIn(self.target.id, member_user_ids)

    def test_superuser_cannot_see_retired_group_leader_in_groups_api(self):
        self._retire_target()
        self.api.force_authenticate(self.superuser)
        r = self.api.get(reverse("api_retreat_event_groups", args=[self.event.id]))
        self.assertEqual(r.status_code, 200, r.content)
        group = next(item for item in r.data if item["id"] == self.group.id)
        member_user_ids = {m["user"] for m in group["memberships"]}
        self.assertNotIn(self.target.id, member_user_ids)
