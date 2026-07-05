"""픽업 담당 관찰자 + 조장/부조장 겸직 — 본인 조 / 픽업 전체 범위."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse

from retreat.models import RetreatCouncilMembership, RetreatGroupMembership
from retreat.tests.fixtures.council_matrix_fixture import CouncilMatrixFixture
from users.permissions import visible_retreat_groups_for

User = get_user_model()


class PickupObserverLeaderMatrixTests(CouncilMatrixFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.pickup_observer_vice = User.objects.create_user(
            username="cm_pickup_obs_vice", password="x"
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.pickup_observer_vice,
            role=RetreatCouncilMembership.Role.PICKUP_OBSERVER,
        )
        RetreatGroupMembership.objects.create(
            user=cls.pickup_observer_vice,
            group=cls.group_seoul,
            role=RetreatGroupMembership.Role.VICE_LEADER,
        )

    def setUp(self):
        self.auth_as(self.pickup_observer_vice)

    def test_dashboard_and_groups_show_own_group_only(self):
        visible_ids = set(
            visible_retreat_groups_for(self.user, self.event).values_list("id", flat=True)
        )
        self.assertEqual(visible_ids, {self.group_seoul.id})

        r = self.page.get(reverse("retreat_dashboard", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_show_dashboard_tab"])
        self.assertTrue(r.context["can_show_groups_tab"])
        self.assertTrue(r.context["can_show_pickup_tab"])

        r2 = self.page.get(reverse("retreat_group_manage_list", args=[self.event.id]))
        self.assertEqual(r2.status_code, 200)
        group_ids = {g.id for g in r2.context["groups"]}
        self.assertEqual(group_ids, {self.group_seoul.id})

    def test_dashboard_api_own_group_only(self):
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.api.get(url).json()
        group_ids = {row["group_id"] for row in data["by_group"]}
        self.assertEqual(group_ids, {self.group_seoul.id})

    def test_pickup_sees_all_groups(self):
        list_url = (
            reverse("api_retreat_event_pickups", args=[self.event.id])
            + "?direction=arrival"
        )
        data = self.api.get(list_url).json()
        group_ids = {row["group"] for row in data}
        self.assertIn(self.group_seoul.id, group_ids)
        self.assertIn(self.group_incheon.id, group_ids)

    def test_pickup_mutate_own_group_only(self):
        incheon_detail = reverse(
            "api_retreat_pickup_detail", args=[self.incheon_arrival_pickup.id]
        )
        r = self.api.patch(
            incheon_detail, {"boarding_place": "변경"}, format="json"
        )
        self.assertEqual(r.status_code, 403, r.content)

        seoul_detail = reverse(
            "api_retreat_pickup_detail", args=[self.arrival_pickup.id]
        )
        r2 = self.api.patch(
            seoul_detail, {"boarding_place": "변경"}, format="json"
        )
        self.assertEqual(r2.status_code, 200, r2.content)
