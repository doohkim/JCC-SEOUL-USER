"""집회 전체 관찰자(event_observer) 권한 매트릭스 — API·페이지 통합 테스트."""

from __future__ import annotations

from django.urls import reverse

from retreat.tests.fixtures.council_matrix_fixture import CouncilMatrixFixture


class EventObserverDropdownTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.event_observer)

    def test_sees_all_active_events_in_picker(self):
        r = self.page.get(reverse("retreat_dashboard", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        available_ids = {ev.id for ev in r.context["available_events"]}
        self.assertIn(self.event.id, available_ids)
        self.assertIn(self.other_event.id, available_ids)
        self.assertContains(
            r, reverse("retreat_staff_apply", args=[self.other_event.id])
        )
        self.assertNotContains(
            r, reverse("retreat_dashboard", args=[self.other_event.id])
        )

    def test_unassigned_event_forbidden(self):
        r = self.page.get(reverse("retreat_dashboard", args=[self.other_event.id]))
        self.assertEqual(r.status_code, 403)


class EventObserverPageTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.event_observer)

    def test_main_pages_return_200(self):
        pages = [
            reverse("retreat_dashboard", args=[self.event.id]),
            reverse("retreat_group_manage_list", args=[self.event.id]),
            reverse("retreat_pickup", args=[self.event.id]) + "?tab=arrival",
            reverse("retreat_pickup", args=[self.event.id]) + "?tab=departure",
            reverse("retreat_pickup", args=[self.event.id]) + "?tab=all",
            reverse("retreat_lodging", args=[self.event.id]),
            reverse("retreat_lodging_roster", args=[self.event.id]),
        ]
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.page.get(url).status_code, 200)

    def test_admin_pages_forbidden(self):
        pages = [
            reverse("retreat_council", args=[self.event.id]),
            reverse("retreat_timetable", args=[self.event.id]),
            reverse("retreat_admin", args=[self.event.id]),
        ]
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.page.get(url).status_code, 403)

    def test_admin_tab_hidden(self):
        r = self.page.get(reverse("retreat_dashboard", args=[self.event.id]))
        self.assertFalse(r.context["can_show_admin_tab"])

    def test_group_list_no_add_button(self):
        r = self.page.get(reverse("retreat_group_manage_list", args=[self.event.id]))
        self.assertFalse(r.context["can_add_group"])
        self.assertNotContains(r, "btnAddGroup")

    def test_group_detail_read_only_flags(self):
        r = self.page.get(
            reverse(
                "retreat_group_manage",
                args=[self.event.id, self.group_seoul.id],
            )
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context["can_add_attendee"])
        self.assertFalse(r.context["can_change_status"])
        self.assertFalse(r.context["can_link_attendee_user"])

    def test_pickup_no_manage_buttons(self):
        r = self.page.get(
            reverse("retreat_pickup", args=[self.event.id]) + "?tab=arrival"
        )
        self.assertFalse(r.context["can_manage_pickup"])
        self.assertFalse(r.context["can_delete_pickup"])
        self.assertNotContains(r, "btnPickupAdd")
        self.assertNotContains(r, "data-pickup-delete")

    def test_lodging_read_only_no_manage_buttons(self):
        r = self.page.get(reverse("retreat_lodging", args=[self.event.id]))
        self.assertFalse(r.context["can_manage_lodging"])
        self.assertNotContains(r, "btnAddLodging")

    def test_council_and_admin_forbidden(self):
        self.assertEqual(
            self.page.get(reverse("retreat_council", args=[self.event.id])).status_code,
            403,
        )


class EventObserverApiTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.event_observer)

    def test_cannot_patch_attendee(self):
        url = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        r = self.api.patch(url, {"name": "변경"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_cannot_add_group(self):
        url = reverse("api_retreat_event_groups", args=[self.event.id])
        r = self.api.post(
            url,
            {
                "name": "신규조",
                "region": self.seoul.id,
                "division": self.div_seoul.id,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_pickup_list_ok_mutations_forbidden(self):
        list_url = (
            reverse("api_retreat_event_pickups", args=[self.event.id])
            + "?direction=arrival"
        )
        self.assertEqual(self.api.get(list_url).status_code, 200)
        r = self.api.post(list_url, self.pickup_post_payload(), format="json")
        self.assertEqual(r.status_code, 403)
        detail = reverse("api_retreat_pickup_detail", args=[self.arrival_pickup.id])
        self.assertEqual(
            self.api.patch(detail, {"boarding_place": "변경"}, format="json").status_code,
            403,
        )
        self.assertEqual(self.api.delete(detail).status_code, 403)

    def test_lodging_post_forbidden(self):
        url = reverse("api_retreat_event_lodgings", args=[self.event.id])
        r = self.api.post(url, {"name": "신규숙소"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_council_get_forbidden(self):
        url = reverse("api_retreat_event_council", args=[self.event.id])
        self.assertEqual(self.api.get(url).status_code, 403)

    def test_timetable_get_forbidden(self):
        url = reverse("api_retreat_event_timetable", args=[self.event.id])
        self.assertEqual(self.api.get(url).status_code, 403)

    def test_timetable_post_forbidden(self):
        url = reverse("api_retreat_event_timetable", args=[self.event.id])
        r = self.api.post(
            url,
            {
                "day": "2026-08-02",
                "start_time": "14:00",
                "end_time": "15:00",
                "title": "집회예배",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_changelog_view_forbidden(self):
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        self.assertEqual(self.api.get(url).status_code, 403)

    def test_dashboard_includes_all_groups(self):
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.api.get(url).json()
        group_ids = {row["group_id"] for row in data["by_group"]}
        self.assertEqual(
            group_ids, {self.group_seoul.id, self.group_incheon.id}
        )
