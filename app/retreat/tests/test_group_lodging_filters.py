"""조별 관리 숙소 미배정 집계·권한 범위."""

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from retreat.models import (
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
from retreat.views import RetreatDashboardView, RetreatGroupManageListView
from users.models import Division, Region, UserDivisionTeam

User = get_user_model()


class GroupLodgingFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.region,
            code="group_lodging_filter",
            name="미배정필터부",
        )
        cls.event = RetreatEvent.objects.create(
            name="미배정 필터 집회",
            start_date=date(2026, 7, 29),
            end_date=date(2026, 7, 31),
        )
        cls.own_group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.region,
            division=cls.division,
            name="담당조",
        )
        cls.other_group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.region,
            division=cls.division,
            name="다른조",
        )
        cls.leader = User.objects.create_user(
            username="group_lodging_leader",
            password="x",
        )
        UserDivisionTeam.objects.create(
            user=cls.leader,
            division=cls.division,
            is_primary=True,
        )
        RetreatGroupMembership.objects.create(
            user=cls.leader,
            group=cls.own_group,
            role=RetreatGroupMembership.Role.LEADER,
        )
        expected = timezone.make_aware(datetime(2026, 7, 29, 10, 0))
        RetreatAttendee.objects.create(
            group=cls.own_group,
            name="미배정 조원",
            expected_check_in_at=expected,
        )
        RetreatAttendee.objects.create(
            group=cls.own_group,
            name="숙박하지 않는 조원",
        )
        RetreatAttendee.objects.create(
            group=cls.other_group,
            name="다른 조 미배정",
            expected_check_in_at=expected,
        )

    def setUp(self):
        self.factory = RequestFactory()

    def _context(self, view_class, path, **kwargs):
        request = self.factory.get(path, {"lodgingStay": "unassigned"})
        request.user = self.leader
        view = view_class()
        view.setup(request, **kwargs)
        view.request = request
        view.kwargs = kwargs
        return view.get_context_data(**kwargs)

    def test_group_list_counts_unassigned_only_in_visible_groups(self):
        path = reverse("retreat_group_manage_list", args=[self.event.id])
        ctx = self._context(
            RetreatGroupManageListView,
            path,
            event_id=self.event.id,
        )
        self.assertTrue(ctx["filter_lodging_unassigned"])
        self.assertEqual([group.id for group in ctx["groups"]], [self.own_group.id])
        self.assertEqual(ctx["groups"][0].lodging_unassigned_count, 1)

    def test_leader_dashboard_can_link_to_scoped_group_list(self):
        path = reverse("retreat_dashboard", args=[self.event.id])
        ctx = self._context(
            RetreatDashboardView,
            path,
            event_id=self.event.id,
        )
        self.assertFalse(ctx["can_show_group_roster"])
        self.assertTrue(ctx["can_use_unassigned_group_link"])
