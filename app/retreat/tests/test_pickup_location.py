"""탑승장소 목록 관리 권한·CRUD 테스트."""

from __future__ import annotations

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from retreat.models import (
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatPickup,
    RetreatPickupLocation,
)
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class _PickupLocationFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.jangseong, _ = Region.objects.get_or_create(
            code="jangseong",
            defaults={"name": "장성", "sort_order": 99},
        )
        cls.div = Division.objects.create(
            region=cls.seoul, code="ploc_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="탑승장소 테스트",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.jangseong,
            division=cls.div,
            name="1조",
        )

        cls.rl_pastor, _ = RoleLevel.objects.get_or_create(
            code="pastor",
            defaults={"name": "목사", "level": 90, "sort_order": 5},
        )
        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president",
            defaults={"name": "회장", "level": 80, "sort_order": 20},
        )

        cls.superuser = User.objects.create_superuser(
            username="ploc_super", password="x"
        )

        cls.council = User.objects.create_user(username="ploc_council", password="x")
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

        cls.leader = User.objects.create_user(username="ploc_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.pastor = User.objects.create_user(username="ploc_pastor", password="x")
        cls.pastor.role_level = cls.rl_pastor
        cls.pastor.save()
        UserDivisionTeam.objects.create(
            user=cls.pastor, division=cls.div, is_primary=True
        )

        cls.staff = User.objects.create_user(username="ploc_staff", password="x")
        cls.staff.role_level = cls.rl_president
        cls.staff.save()

        cls.location = RetreatPickupLocation.objects.create(
            event=cls.event,
            name="장성역",
            sort_order=1,
            created_by=cls.council,
        )

    def setUp(self):
        self.client = APIClient()
        self.page_client = Client()

    def _list_url(self):
        return reverse("api_retreat_event_pickup_locations", args=[self.event.id])

    def _detail_url(self, loc_id=None):
        return reverse(
            "api_retreat_pickup_location_detail",
            args=[loc_id or self.location.id],
        )


class PickupLocationApiPermissionTests(_PickupLocationFixture):
    def test_council_can_list_locations(self):
        self.client.force_authenticate(self.council)
        r = self.client.get(self._list_url())
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()), 1)

    def test_superuser_can_create_location(self):
        self.client.force_authenticate(self.superuser)
        r = self.client.post(
            self._list_url(),
            {"name": "장성 터미널"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(
            RetreatPickupLocation.objects.filter(
                event=self.event, name="장성 터미널"
            ).exists()
        )

    def test_leader_cannot_list_manage_api(self):
        self.client.force_authenticate(self.leader)
        r = self.client.get(self._list_url())
        self.assertEqual(r.status_code, 403)

    def test_pastor_cannot_create_location(self):
        self.client.force_authenticate(self.pastor)
        r = self.client.post(
            self._list_url(),
            {"name": "X"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_staff_without_council_membership_forbidden(self):
        self.client.force_authenticate(self.staff)
        r = self.client.get(self._list_url())
        self.assertEqual(r.status_code, 403)

    def test_council_can_patch_and_delete(self):
        self.client.force_authenticate(self.council)
        r = self.client.patch(
            self._detail_url(),
            {"name": "장성역(수정)"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "장성역(수정)")

        r = self.client.delete(self._detail_url())
        self.assertEqual(r.status_code, 204)
        self.assertFalse(
            RetreatPickupLocation.objects.filter(pk=self.location.id).exists()
        )


class PickupLocationPageTests(_PickupLocationFixture):
    def test_council_sees_manage_flag_and_location_json(self):
        self.page_client.force_login(self.council)
        r = self.page_client.get(reverse("retreat_pickup", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_pickup_location"])
        self.assertIn("장성역", r.context["pickup_location_choices_json"])
        self.assertContains(r, "탑승장소 관리")

    def test_leader_does_not_see_manage_ui(self):
        self.page_client.force_login(self.leader)
        r = self.page_client.get(reverse("retreat_pickup", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context["can_manage_pickup_location"])
        self.assertNotContains(r, "탑승장소 관리")
        self.assertIn("장성역", r.context["pickup_location_choices_json"])

    def test_pastor_without_staff_cannot_access_pickup_page(self):
        self.page_client.force_login(self.pastor)
        r = self.page_client.get(reverse("retreat_pickup", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)


class PickupBoardingPlaceValidationTests(_PickupLocationFixture):
    def test_pickup_post_rejects_unlisted_boarding_place(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(
            reverse("api_retreat_event_pickups", args=[self.event.id]),
            {
                "direction": "arrival",
                "name": "테스트",
                "region": self.jangseong.id,
                "train_time": timezone.make_aware(
                    datetime(2026, 8, 1, 10, 30)
                ).isoformat(),
                "boarding_place": "존재하지않는역",
                "contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("boarding_place", r.json())

    def test_pickup_post_accepts_listed_boarding_place(self):
        self.client.force_authenticate(self.council)
        r = self.client.post(
            reverse("api_retreat_event_pickups", args=[self.event.id]),
            {
                "direction": "arrival",
                "name": "테스트",
                "region": self.jangseong.id,
                "train_time": timezone.make_aware(
                    datetime(2026, 8, 1, 10, 30)
                ).isoformat(),
                "boarding_place": "장성역",
                "contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        pickup = RetreatPickup.objects.get(pk=r.json()["id"])
        self.assertEqual(pickup.boarding_place, "장성역")
