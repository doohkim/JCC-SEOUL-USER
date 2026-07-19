"""변경 이력 API 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from retreat.models import (
    RetreatAttendee,
    RetreatChangeLog,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatSession,
    RetreatSessionAttendee,
)
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class RetreatChangelogTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="log_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="로그 테스트",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
        )
        cls.session = RetreatSession.objects.create(event=cls.event, name="세션")
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="A",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.enrollment = RetreatSessionAttendee.objects.create(
            session=cls.session,
            source_attendee=cls.attendee,
            source_group=cls.group,
            name=cls.attendee.name,
            phone=cls.attendee.phone,
            gender=cls.attendee.gender,
            check_in_status=cls.attendee.check_in_status,
            group_name=cls.group.name,
            region_id_snapshot=cls.group.region_id,
            region_name=cls.group.region.name,
            division_id_snapshot=cls.group.division_id,
            division_name=cls.group.division.name,
        )
        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president", defaults={"name": "회장", "level": 80, "sort_order": 20}
        )
        cls.staff = User.objects.create_user(username="log_staff", password="x")
        cls.staff.role_level = cls.rl_president
        cls.staff.save()
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.div, is_primary=True
        )
        cls.leader = User.objects.create_user(username="log_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

    def setUp(self):
        self.client = APIClient()

    def test_attendance_upsert_creates_changelog(self):
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_attendance_bulk_upsert")
        r = self.client.post(
            url,
            {
                "session_id": self.session.id,
                "rows": [{"attendee_id": self.attendee.id, "status": "present"}],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            RetreatChangeLog.objects.filter(
                target_type=RetreatChangeLog.TargetType.ATTENDANCE,
                action=RetreatChangeLog.Action.CREATE,
            ).exists()
        )

    def test_changelog_forbidden_for_leader(self):
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_changelog_forbidden_for_event_observer(self):
        from retreat.models import RetreatCouncilMembership

        observer = User.objects.create_user(username="log_observer", password="x")
        RetreatCouncilMembership.objects.create(
            event=self.event,
            user=observer,
            role=RetreatCouncilMembership.Role.EVENT_OBSERVER,
        )
        self.client.force_authenticate(observer)
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        self.assertEqual(self.client.get(url).status_code, 403)
