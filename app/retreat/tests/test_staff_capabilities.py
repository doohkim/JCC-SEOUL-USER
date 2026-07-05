"""집회 운영진 RBAC capability 매트릭스 테스트."""

from __future__ import annotations

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatPickup,
)
from retreat.services.staff_capabilities import (
    AccessLevel,
    effective_capabilities,
    pickup_tab_access_level,
)
from users.models import Division, Region

User = get_user_model()


class _StaffRbacFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.incheon = Region.objects.get(code="incheon")
        cls.div_seoul = Division.objects.create(
            region=cls.seoul, code="rbac_seoul_y", name="서울청년"
        )
        cls.div_incheon = Division.objects.create(
            region=cls.incheon, code="rbac_ic_y", name="인천청년"
        )
        cls.event = RetreatEvent.objects.create(
            name="RBAC 집회",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.group_seoul = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_seoul,
            name="서울1조",
        )
        cls.group_incheon = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.incheon,
            division=cls.div_incheon,
            name="인천1조",
        )

    @classmethod
    def _staff(cls, username: str, role: str, **scope) -> User:
        user = User.objects.create_user(username=username, password="x")
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=user,
            role=role,
            **scope,
        )
        return user


class StaffCapabilitiesUnitTests(_StaffRbacFixture):
    def test_event_admin_caps(self):
        admin = self._staff("rbac_admin", RetreatCouncilMembership.Role.EVENT_ADMIN)
        caps = effective_capabilities(admin, self.event)
        self.assertTrue(caps.add_group)
        self.assertEqual(caps.pickup_arrival, AccessLevel.MUTATE)
        self.assertTrue(caps.delete_pickup)
        self.assertFalse(caps.delete_checked_out_attendee)

    def test_superuser_caps(self):
        user = User.objects.create_superuser(username="rbac_su_caps", password="x")
        caps = effective_capabilities(user, self.event)
        self.assertTrue(caps.delete_checked_out_attendee)
        self.assertTrue(caps.delete_pickup)

    def test_event_observer_caps(self):
        obs = self._staff(
            "rbac_event_obs", RetreatCouncilMembership.Role.EVENT_OBSERVER
        )
        caps = effective_capabilities(obs, self.event)
        self.assertEqual(caps.groups, AccessLevel.VIEW)
        self.assertFalse(caps.add_group)
        self.assertEqual(caps.admin, AccessLevel.NONE)
        self.assertFalse(caps.view_staff)
        self.assertFalse(caps.view_changelog)
        self.assertEqual(caps.pickup_arrival, AccessLevel.VIEW)
        self.assertFalse(caps.delete_pickup)

    def test_pickup_observer_caps(self):
        obs = self._staff(
            "rbac_pickup_obs", RetreatCouncilMembership.Role.PICKUP_OBSERVER
        )
        caps = effective_capabilities(obs, self.event)
        self.assertEqual(caps.dashboard, AccessLevel.NONE)
        self.assertEqual(caps.pickup, AccessLevel.VIEW)
        self.assertEqual(
            pickup_tab_access_level(caps, "overview"), AccessLevel.VIEW
        )
        self.assertFalse(caps.delete_pickup)

    def test_region_admin_caps(self):
        admin = self._staff(
            "rbac_region",
            RetreatCouncilMembership.Role.REGION_ADMIN,
            region=self.seoul,
        )
        caps = effective_capabilities(admin, self.event)
        self.assertEqual(caps.scope.kind, "region")
        self.assertEqual(caps.scope.region_id, self.seoul.id)
        self.assertTrue(caps.add_attendee)
        self.assertFalse(caps.link_attendee_user)
        self.assertEqual(caps.pickup_arrival, AccessLevel.MUTATE)
        self.assertFalse(caps.delete_pickup)
        self.assertEqual(caps.lodging, AccessLevel.NONE)

    def test_region_observer_caps(self):
        obs = self._staff(
            "rbac_region_obs",
            RetreatCouncilMembership.Role.REGION_OBSERVER,
            region=self.seoul,
        )
        caps = effective_capabilities(obs, self.event)
        self.assertEqual(caps.scope.kind, "region")
        self.assertFalse(caps.add_attendee)
        self.assertEqual(caps.pickup_arrival, AccessLevel.VIEW)

    def test_division_admin_caps(self):
        admin = self._staff(
            "rbac_division",
            RetreatCouncilMembership.Role.DIVISION_ADMIN,
            division=self.div_seoul,
        )
        caps = effective_capabilities(admin, self.event)
        self.assertEqual(caps.scope.kind, "division")
        self.assertEqual(caps.scope.division_id, self.div_seoul.id)
        self.assertTrue(caps.add_attendee)
        self.assertFalse(caps.delete_pickup)

    def test_division_observer_caps(self):
        obs = self._staff(
            "rbac_division_obs",
            RetreatCouncilMembership.Role.DIVISION_OBSERVER,
            division=self.div_seoul,
        )
        caps = effective_capabilities(obs, self.event)
        self.assertEqual(caps.scope.kind, "division")
        self.assertFalse(caps.add_attendee)


class StaffRbacApiTests(_StaffRbacFixture):
    def setUp(self):
        self.client = APIClient()
        self.event_admin = self._staff(
            "rbac_api_admin", RetreatCouncilMembership.Role.EVENT_ADMIN
        )
        self.event_observer = self._staff(
            "rbac_api_obs", RetreatCouncilMembership.Role.EVENT_OBSERVER
        )
        self.region_admin = self._staff(
            "rbac_api_region",
            RetreatCouncilMembership.Role.REGION_ADMIN,
            region=self.seoul,
        )
        self.pickup_observer = self._staff(
            "rbac_api_pickup", RetreatCouncilMembership.Role.PICKUP_OBSERVER
        )
        self.superuser = User.objects.create_superuser(
            username="rbac_super", password="x"
        )
        self.attendee = RetreatAttendee.objects.create(
            group=self.group_seoul, name="대상"
        )
        self.checked_out = RetreatAttendee.objects.create(
            group=self.group_seoul,
            name="퇴실자",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )

    def test_event_admin_can_add_group(self):
        self.client.force_authenticate(self.event_admin)
        r = self.client.post(
            reverse("api_retreat_event_groups", args=[self.event.id]),
            {
                "name": "신규조",
                "region": self.seoul.id,
                "division": self.div_seoul.id,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)

    def test_event_observer_cannot_patch_attendee(self):
        self.client.force_authenticate(self.event_observer)
        url = reverse("api_retreat_attendee_detail", args=[self.attendee.id])
        r = self.client.patch(url, {"name": "변경"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    def test_event_observer_cannot_access_council_api(self):
        self.client.force_authenticate(self.event_observer)
        url = reverse("api_retreat_event_council", args=[self.event.id])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_region_admin_cannot_access_out_of_scope_group(self):
        self.client.force_authenticate(self.region_admin)
        url = reverse("api_retreat_group_attendees", args=[self.group_incheon.id])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_region_admin_can_patch_profile_not_user_link(self):
        self.client.force_authenticate(self.region_admin)
        url = reverse("api_retreat_attendee_detail", args=[self.attendee.id])
        r = self.client.patch(url, {"name": "지역관리수정"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        other = User.objects.create_user(username="link_target", password="x")
        r = self.client.patch(url, {"user": other.id}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    def test_pickup_observer_dashboard_page_forbidden(self):
        from django.test import Client

        client = Client()
        client.force_login(self.pickup_observer)
        r = client.get(reverse("retreat_dashboard", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)

    def test_pickup_observer_can_list_pickup_cannot_create(self):
        self.client.force_authenticate(self.pickup_observer)
        list_url = reverse("api_retreat_event_pickups", args=[self.event.id]) + "?direction=arrival"
        self.assertEqual(self.client.get(list_url).status_code, 200)
        r = self.client.post(
            list_url,
            {
                "direction": "arrival",
                "name": "신규",
                "group": self.group_seoul.id,
                "region": self.seoul.id,
                "division": self.div_seoul.id,
                "train_time": "2026-08-01T10:00:00+09:00",
                "boarding_place": "역",
                "contact": "01012345678",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 403, r.content)

    def test_event_admin_cannot_delete_checked_out_attendee(self):
        self.client.force_authenticate(self.event_admin)
        url = reverse("api_retreat_attendee_detail", args=[self.checked_out.id])
        self.assertEqual(self.client.delete(url).status_code, 403)

    def test_superuser_can_delete_checked_out_attendee(self):
        self.client.force_authenticate(self.superuser)
        url = reverse("api_retreat_attendee_detail", args=[self.checked_out.id])
        self.assertEqual(self.client.delete(url).status_code, 200)

    def test_region_admin_cannot_delete_pickup(self):
        pickup = RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=99,
            group=self.group_seoul,
            name="삭제테스트",
            region=self.seoul,
            division=self.div_seoul,
            train_time=timezone.make_aware(datetime(2026, 8, 1, 10, 0)),
            boarding_place="역",
            contact="01099998888",
        )
        self.client.force_authenticate(self.region_admin)
        url = reverse("api_retreat_pickup_detail", args=[pickup.id])
        self.assertEqual(self.client.delete(url).status_code, 403)
