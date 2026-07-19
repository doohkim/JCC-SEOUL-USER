"""지역 관리자·관찰자(region_admin/observer) 권한 매트릭스."""

from __future__ import annotations

from django.urls import reverse

from retreat.models import RetreatAttendee, RetreatGroup, RetreatGroupScope
from retreat.tests.fixtures.council_matrix_fixture import CouncilMatrixFixture


class RegionAdminScopeTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.region_admin)

    def test_dashboard_scoped_to_region(self):
        shared_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.incheon,
            division=self.div_incheon,
            name="공유인천1조",
        )
        RetreatGroupScope.objects.create(
            group=shared_group,
            region=self.seoul,
            division=self.div_seoul,
        )
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.api.get(url).json()
        group_ids = {row["group_id"] for row in data["by_group"]}
        self.assertEqual(group_ids, {self.group_seoul.id, shared_group.id})
        rollup_division_ids = {row["division_id"] for row in data["by_division"]}
        self.assertEqual(rollup_division_ids, {self.div_seoul.id})

    def test_group_board_scoped(self):
        url = reverse("api_retreat_event_group_board", args=[self.event.id])
        names = {g["name"] for g in self.api.get(url).json()["groups"]}
        self.assertEqual(names, {"서울1조"})

    def test_incheon_group_attendees_forbidden(self):
        url = reverse("api_retreat_group_attendees", args=[self.group_incheon.id])
        self.assertEqual(self.api.get(url).status_code, 403)

    def test_lodging_pages_forbidden(self):
        for url in [
            reverse("retreat_lodging", args=[self.event.id]),
            reverse("retreat_lodging_roster", args=[self.event.id]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.page.get(url).status_code, 403)

    def test_admin_pages_forbidden(self):
        for url in [
            reverse("retreat_council", args=[self.event.id]),
            reverse("retreat_timetable", args=[self.event.id]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.page.get(url).status_code, 403)


class RegionAdminAttendeeTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.region_admin)

    def test_can_add_and_patch_profile(self):
        url = reverse("api_retreat_group_attendees", args=[self.group_seoul.id])
        r = self.api.post(url, {"name": "지역신규"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        detail = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        r2 = self.api.patch(
            detail, {"name": "지역수정", "phone": "01011112222"}, format="json"
        )
        self.assertEqual(r2.status_code, 200, r2.content)

    def test_cannot_link_user_or_change_check_in(self):
        detail = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        r = self.api.patch(
            detail,
            {"user": self.link_user.id, "check_in_status": "checked_in"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_cannot_delete_attendee(self):
        detail = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        self.assertEqual(self.api.delete(detail).status_code, 403)

    def test_group_detail_flags(self):
        r = self.page.get(
            reverse(
                "retreat_group_manage",
                args=[self.event.id, self.group_seoul.id],
            )
        )
        self.assertTrue(r.context["can_add_attendee"])
        self.assertFalse(r.context["can_change_status"])
        self.assertFalse(r.context["can_link_attendee_user"])


class RegionAdminPickupTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.region_admin)

    def test_arrival_post_ok(self):
        RetreatAttendee.objects.create(group=self.group_seoul, name="픽업신규")
        url = reverse("api_retreat_event_pickups", args=[self.event.id])
        r = self.api.post(url, self.pickup_post_payload(name="픽업신규"), format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def test_pickup_patch_ok_delete_forbidden(self):
        detail = reverse("api_retreat_pickup_detail", args=[self.arrival_pickup.id])
        r = self.api.patch(detail, {"boarding_place": "수정역"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.api.delete(detail).status_code, 403)

    def test_overview_tab_no_add_button(self):
        r = self.page.get(reverse("retreat_pickup", args=[self.event.id]) + "?tab=all")
        self.assertFalse(r.context["can_manage_pickup"])

    def test_arrival_tab_manage_no_delete(self):
        r = self.page.get(
            reverse("retreat_pickup", args=[self.event.id]) + "?tab=arrival"
        )
        self.assertTrue(r.context["can_manage_pickup"])
        self.assertFalse(r.context["can_delete_pickup"])
        self.assertContains(r, "btnPickupAdd")
        self.assertNotContains(r, "data-pickup-delete")

    def test_cannot_mutate_incheon_pickup(self):
        detail = reverse(
            "api_retreat_pickup_detail", args=[self.incheon_arrival_pickup.id]
        )
        self.assertEqual(
            self.api.patch(
                detail, {"boarding_place": "인천역"}, format="json"
            ).status_code,
            403,
        )


class RegionObserverTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.region_observer)

    def test_scoped_dashboard(self):
        shared_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.incheon,
            division=self.div_incheon,
            name="공유인천2조",
        )
        RetreatGroupScope.objects.create(
            group=shared_group,
            region=self.seoul,
            division=self.div_seoul,
        )
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        group_ids = {row["group_id"] for row in self.api.get(url).json()["by_group"]}
        self.assertEqual(group_ids, {self.group_seoul.id, shared_group.id})

    def test_group_list_no_add(self):
        r = self.page.get(reverse("retreat_group_manage_list", args=[self.event.id]))
        self.assertFalse(r.context["can_add_group"])
        self.assertNotContains(r, "btnAddGroup")

    def test_attendee_patch_forbidden(self):
        detail = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        self.assertEqual(
            self.api.patch(detail, {"name": "x"}, format="json").status_code, 403
        )

    def test_pickup_view_only(self):
        list_url = (
            reverse("api_retreat_event_pickups", args=[self.event.id])
            + "?direction=arrival"
        )
        self.assertEqual(self.api.get(list_url).status_code, 200)
        self.assertEqual(
            self.api.post(
                list_url, self.pickup_post_payload(), format="json"
            ).status_code,
            403,
        )
        detail = reverse("api_retreat_pickup_detail", args=[self.arrival_pickup.id])
        self.assertEqual(
            self.api.patch(detail, {"boarding_place": "x"}, format="json").status_code,
            403,
        )
