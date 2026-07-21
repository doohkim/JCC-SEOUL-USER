"""변경 이력 API 테스트."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from retreat.models import (
    RetreatAttendee,
    RetreatChangeLog,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatSession,
    RetreatSessionAttendee,
)
from users.models import Division, Region, RoleLevel, UserDivisionTeam, UserProfile

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

        cls.admin = User.objects.create_user(username="log_admin", password="x")
        UserDivisionTeam.objects.create(
            user=cls.admin, division=cls.div, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.admin,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )
        UserProfile.objects.update_or_create(
            user=cls.admin, defaults={"display_name": "관리자김", "real_name": "김관리"}
        )
        cls.other = User.objects.create_user(username="log_other", password="x")
        UserProfile.objects.update_or_create(
            user=cls.other, defaults={"display_name": "다른사람", "real_name": "이다른"}
        )

        now = timezone.now()
        for i in range(25):
            log = RetreatChangeLog.objects.create(
                event=cls.event,
                action=(
                    RetreatChangeLog.Action.UPDATE
                    if i % 2
                    else RetreatChangeLog.Action.CREATE
                ),
                target_type=(
                    RetreatChangeLog.TargetType.ATTENDEE
                    if i % 3
                    else RetreatChangeLog.TargetType.GROUP_MEMBERSHIP
                ),
                target_id=1000 + i,
                payload_before={"name": f"이전{i}"},
                payload_after={"name": f"김민혁-{i}" if i == 5 else f"이후{i}"},
                changed_by=cls.admin if i < 15 else cls.other,
            )
            RetreatChangeLog.objects.filter(pk=log.pk).update(
                changed_at=now - timedelta(days=i // 10)
            )

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
        observer = User.objects.create_user(username="log_observer", password="x")
        RetreatCouncilMembership.objects.create(
            event=self.event,
            user=observer,
            role=RetreatCouncilMembership.Role.EVENT_OBSERVER,
        )
        self.client.force_authenticate(observer)
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_changelog_api_paginated_shape(self):
        self.client.force_authenticate(self.admin)
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("count", body)
        self.assertIn("page", body)
        self.assertIn("page_size", body)
        self.assertIn("results", body)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 20)
        self.assertEqual(len(body["results"]), 20)
        self.assertGreaterEqual(body["count"], 25)

    def test_changelog_api_page_two(self):
        self.client.force_authenticate(self.admin)
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        r = self.client.get(url, {"page": 2})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["page"], 2)
        self.assertEqual(len(body["results"]), body["count"] - 20)

    def test_changelog_api_filter_actor_and_target(self):
        self.client.force_authenticate(self.admin)
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        r = self.client.get(
            url,
            {
                "actor": self.admin.id,
                "target_type": RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            },
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        for row in body["results"]:
            self.assertEqual(row["changed_by"], self.admin.id)
            self.assertEqual(
                row["target_type"], RetreatChangeLog.TargetType.GROUP_MEMBERSHIP
            )

    def test_changelog_api_filter_action_and_q(self):
        self.client.force_authenticate(self.admin)
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        # i=5 → UPDATE + payload "김민혁-5"
        r = self.client.get(
            url,
            {"action": RetreatChangeLog.Action.UPDATE, "q": "김민혁"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertGreaterEqual(body["count"], 1)
        for row in body["results"]:
            self.assertEqual(row["action"], RetreatChangeLog.Action.UPDATE)

    def test_changelog_api_date_filter(self):
        self.client.force_authenticate(self.admin)
        today = timezone.localdate()
        url = reverse("api_retreat_event_changelog", args=[self.event.id])
        r = self.client.get(
            url,
            {"date_from": today.isoformat(), "date_to": today.isoformat()},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertGreaterEqual(body["count"], 1)
        self.assertLess(body["count"], 25)
