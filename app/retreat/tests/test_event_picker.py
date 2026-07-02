"""집회 드롭다운 서비스 단위 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from retreat.models import (
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
from retreat.services.event_picker import (
    active_retreat_events,
    default_retreat_event_for,
    picker_target_url,
    retreat_event_for_user,
    set_last_retreat_event,
)
from users.models import Division, Region, UserDivisionTeam

User = get_user_model()


class EventPickerServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="ep_seoul_y", name="청년부"
        )
        cls.later = RetreatEvent.objects.create(
            name="늦은 집회",
            start_date=date(2027, 7, 1),
            end_date=date(2027, 7, 3),
        )
        cls.earlier = RetreatEvent.objects.create(
            name="이른 집회",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
        )
        cls.inactive = RetreatEvent.objects.create(
            name="비활성",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 3),
            is_active=False,
        )

        cls.leader = User.objects.create_user(username="ep_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.earlier,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.applicant = User.objects.create_user(username="ep_applicant", password="x")

    def test_active_retreat_events_ordered_by_start_date_desc(self):
        ids = [ev.id for ev in active_retreat_events()]
        self.assertEqual(ids, [self.later.id, self.earlier.id])
        self.assertNotIn(self.inactive.id, ids)

    def test_default_retreat_event_prefers_operational_access(self):
        self.assertEqual(default_retreat_event_for(self.leader), self.earlier)
        RetreatGroupMembership.objects.create(
            user=self.leader,
            group=RetreatGroup.objects.create(
                event=self.later,
                region=self.seoul,
                division=self.div,
                name="2조",
            ),
        )
        self.assertEqual(default_retreat_event_for(self.leader), self.later)

    def test_default_retreat_event_falls_back_to_first_active(self):
        self.assertEqual(default_retreat_event_for(self.applicant), self.later)

    def test_picker_target_url_without_access_goes_to_staff_apply(self):
        url = picker_target_url(self.applicant, self.earlier, retreat_tab="dashboard")
        self.assertEqual(url, reverse("retreat_staff_apply", args=[self.earlier.id]))

    def test_picker_target_url_with_access_uses_tab(self):
        admin = User.objects.create_user(username="ep_admin", password="x")
        RetreatCouncilMembership.objects.create(
            event=self.later,
            user=admin,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )
        url = picker_target_url(admin, self.later, retreat_tab="results")
        self.assertEqual(url, reverse("retreat_results", args=[self.later.id]))

    def test_retreat_event_for_user_prefers_session(self):
        session = {}
        set_last_retreat_event(session, self.earlier.id)
        self.assertEqual(
            retreat_event_for_user(self.leader, session),
            self.earlier,
        )

    def test_retreat_event_for_user_ignores_inactive_session_event(self):
        session = {}
        set_last_retreat_event(session, self.inactive.id)
        self.assertEqual(
            retreat_event_for_user(self.leader, session),
            self.earlier,
        )

    def test_retreat_event_for_user_falls_back_without_session(self):
        self.assertEqual(
            retreat_event_for_user(self.leader, {}),
            self.earlier,
        )
