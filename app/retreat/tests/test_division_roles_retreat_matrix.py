"""부서 관리자·관찰자(division_admin/observer) 권한 매트릭스."""

from __future__ import annotations

from django.urls import reverse

from retreat.models import RetreatAttendee, RetreatGroup, RetreatGroupScope
from retreat.tests.fixtures.council_matrix_fixture import CouncilMatrixFixture


class DivisionAdminScopeTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.division_admin)

    def test_dashboard_scoped_to_division(self):
        shared_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.incheon,
            division=self.div_incheon,
            name="공유인천3조",
        )
        RetreatGroupScope.objects.create(
            group=shared_group,
            region=self.seoul,
            division=self.div_seoul,
        )
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        group_ids = {
            row["group_id"] for row in self.api.get(url).json()["by_group"]
        }
        self.assertEqual(group_ids, {self.group_seoul.id, shared_group.id})
        rollup_division_ids = {
            row["division_id"] for row in self.api.get(url).json()["by_division"]
        }
        self.assertEqual(rollup_division_ids, {self.div_seoul.id})

    def test_incheon_group_forbidden(self):
        url = reverse("api_retreat_group_attendees", args=[self.group_incheon.id])
        self.assertEqual(self.api.get(url).status_code, 403)

    def test_lodging_and_admin_forbidden(self):
        self.assertEqual(
            self.page.get(reverse("retreat_lodging", args=[self.event.id])).status_code,
            403,
        )
        self.assertEqual(
            self.page.get(reverse("retreat_council", args=[self.event.id])).status_code,
            403,
        )


class DivisionAdminAttendeePickupTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.division_admin)

    def test_add_attendee_and_patch_profile(self):
        url = reverse("api_retreat_group_attendees", args=[self.group_seoul.id])
        self.assertEqual(
            self.api.post(url, {"name": "부서신규"}, format="json").status_code, 201
        )
        detail = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        self.assertEqual(
            self.api.patch(detail, {"gender": "male"}, format="json").status_code, 200
        )

    def test_cannot_link_user(self):
        detail = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        self.assertEqual(
            self.api.patch(detail, {"user": self.link_user.id}, format="json").status_code,
            403,
        )

    def test_pickup_arrival_mutate_no_delete(self):
        RetreatAttendee.objects.create(group=self.group_seoul, name="부서픽업신규")
        url = reverse("api_retreat_event_pickups", args=[self.event.id])
        self.assertEqual(
            self.api.post(
                url,
                self.pickup_post_payload(name="부서픽업신규"),
                format="json",
            ).status_code,
            201,
        )
        detail = reverse("api_retreat_pickup_detail", args=[self.arrival_pickup.id])
        self.assertEqual(
            self.api.patch(detail, {"note": "메모"}, format="json").status_code, 200
        )
        self.assertEqual(self.api.delete(detail).status_code, 403)

    def test_pickup_ui_arrival_manage_no_delete(self):
        r = self.page.get(
            reverse("retreat_pickup", args=[self.event.id]) + "?tab=arrival"
        )
        self.assertTrue(r.context["can_manage_pickup"])
        self.assertFalse(r.context["can_delete_pickup"])


class DivisionObserverTests(CouncilMatrixFixture):
    def setUp(self):
        self.auth_as(self.division_observer)

    def test_scoped_group_list(self):
        shared_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.incheon,
            division=self.div_incheon,
            name="공유인천4조",
        )
        RetreatGroupScope.objects.create(
            group=shared_group,
            region=self.seoul,
            division=self.div_seoul,
        )
        r = self.page.get(reverse("retreat_group_manage_list", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        names = {g.name for g in r.context["groups"]}
        self.assertEqual(names, {"서울1조", shared_group.name})
        self.assertFalse(r.context["can_add_group"])

    def test_attendee_and_pickup_read_only(self):
        detail = reverse("api_retreat_attendee_detail", args=[self.pending.id])
        self.assertEqual(
            self.api.patch(detail, {"name": "x"}, format="json").status_code, 403
        )
        list_url = (
            reverse("api_retreat_event_pickups", args=[self.event.id])
            + "?direction=departure"
        )
        self.assertEqual(self.api.get(list_url).status_code, 200)
        self.assertEqual(
            self.api.post(
                list_url,
                self.pickup_post_payload(
                    direction="departure", name="입실중"
                ),
                format="json",
            ).status_code,
            403,
        )
