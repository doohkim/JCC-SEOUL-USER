"""픽업 담당 관찰자(pickup_observer) 권한 매트릭스."""

from __future__ import annotations

from django.urls import reverse

from retreat.tests.fixtures.council_matrix_fixture import CouncilMatrixFixture


class PickupObserverAccessTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.pickup_observer)

    def test_non_pickup_pages_forbidden(self):
        forbidden = [
            reverse("retreat_dashboard", args=[self.event.id]),
            reverse("retreat_group_manage_list", args=[self.event.id]),
            reverse("retreat_lodging", args=[self.event.id]),
            reverse("retreat_council", args=[self.event.id]),
            reverse("retreat_timetable", args=[self.event.id]),
        ]
        for url in forbidden:
            with self.subTest(url=url):
                self.assertEqual(self.page.get(url).status_code, 403)

    def test_pickup_tabs_accessible(self):
        for tab in ("arrival", "departure", "all"):
            with self.subTest(tab=tab):
                url = reverse("retreat_pickup", args=[self.event.id]) + f"?tab={tab}"
                r = self.page.get(url)
                self.assertEqual(r.status_code, 200)
                self.assertFalse(r.context["can_manage_pickup"])
                self.assertFalse(r.context["can_delete_pickup"])
                self.assertNotContains(r, "btnPickupAdd")

    def test_unassigned_event_forbidden(self):
        r = self.page.get(
            reverse("retreat_pickup", args=[self.other_event.id]) + "?tab=arrival"
        )
        self.assertEqual(r.status_code, 403)


class PickupObserverApiTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.pickup_observer)

    def test_list_all_directions_ok(self):
        base = reverse("api_retreat_event_pickups", args=[self.event.id])
        for direction in ("arrival", "departure"):
            with self.subTest(direction=direction):
                self.assertEqual(
                    self.api.get(base + f"?direction={direction}").status_code, 200
                )

    def test_mutations_forbidden(self):
        list_url = (
            reverse("api_retreat_event_pickups", args=[self.event.id])
            + "?direction=arrival"
        )
        self.assertEqual(
            self.api.post(list_url, self.pickup_post_payload(), format="json").status_code,
            403,
        )
        detail = reverse("api_retreat_pickup_detail", args=[self.arrival_pickup.id])
        self.assertEqual(
            self.api.patch(detail, {"boarding_place": "x"}, format="json").status_code,
            403,
        )
        self.assertEqual(self.api.delete(detail).status_code, 403)

    def test_sees_all_groups_in_pickup_list(self):
        list_url = (
            reverse("api_retreat_event_pickups", args=[self.event.id])
            + "?direction=arrival"
        )
        data = self.api.get(list_url).json()
        group_ids = {row["group"] for row in data}
        self.assertIn(self.group_seoul.id, group_ids)
        self.assertIn(self.group_incheon.id, group_ids)
