"""조원별 변경 이력 API 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.dateparse import parse_datetime
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


class RetreatAttendeeHistoryTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="hist_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="이력 테스트",
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
        cls.other_group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="2조",
        )
        cls.attendee = RetreatAttendee.objects.create(
            group=cls.group,
            name="홍길동",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.other_attendee = RetreatAttendee.objects.create(
            group=cls.other_group,
            name="이순신",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president", defaults={"name": "회장", "level": 80, "sort_order": 20}
        )
        cls.staff = User.objects.create_user(username="hist_staff", password="x")
        cls.staff.role_level = cls.rl_president
        cls.staff.save()
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.div, is_primary=True
        )
        cls.leader = User.objects.create_user(username="hist_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

    def setUp(self):
        self.client = APIClient()

    def _url(self, attendee_id):
        return reverse("api_retreat_attendee_history", args=[attendee_id])

    def test_history_unauthenticated(self):
        r = self.client.get(self._url(self.attendee.id))
        self.assertEqual(r.status_code, 403)

    def test_history_forbidden_for_other_group_leader(self):
        other_leader = User.objects.create_user(username="hist_other", password="x")
        UserDivisionTeam.objects.create(
            user=other_leader, division=self.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(
            user=other_leader, group=self.other_group
        )
        self.client.force_authenticate(other_leader)
        r = self.client.get(self._url(self.attendee.id))
        self.assertEqual(r.status_code, 403)

    def test_history_ok_for_group_leader(self):
        RetreatChangeLog.objects.create(
            event=self.event,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.ATTENDEE,
            target_id=self.attendee.id,
            payload_before={
                "id": self.attendee.id,
                "check_in_status": "pending",
            },
            payload_after={
                "id": self.attendee.id,
                "check_in_status": "checked_in",
            },
            changed_by=self.leader,
        )
        self.client.force_authenticate(self.leader)
        r = self.client.get(self._url(self.attendee.id))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["attendee"]["id"], self.attendee.id)
        self.assertEqual(len(data["check_in_history"]), 1)
        entry = data["check_in_history"][0]
        self.assertEqual(entry["prev_status"], "pending")
        self.assertEqual(entry["next_status"], "checked_in")
        self.assertIn("입실", entry["summary"])

    def test_leader_can_patch_expected_timestamps(self):
        self.assertNotEqual(
            self.attendee.check_in_status,
            RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_attendee_detail", args=[self.attendee.id])
        r = self.client.patch(
            url,
            {
                "expected_check_in_at": "2026-07-01T18:00:00Z",
                "expected_check_out_at": "2026-07-02T12:00:00Z",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body["expected_check_in_at"])
        self.assertTrue(body["expected_check_out_at"])

        hist = self.client.get(self._url(self.attendee.id)).json()
        self.assertTrue(
            any(
                "예상 입실 시각" in (e.get("summary") or "")
                or "예상 퇴실 시각" in (e.get("summary") or "")
                for e in hist["check_in_history"]
            ),
            hist["check_in_history"],
        )
        self.assertEqual(
            parse_datetime(hist["attendee"]["expected_check_in_at"]),
            parse_datetime(body["expected_check_in_at"]),
        )

    def test_history_filters_attendance_to_target_attendee(self):
        enrollment = RetreatSessionAttendee.objects.create(
            session=self.session,
            source_attendee=self.attendee,
            source_group=self.group,
            name=self.attendee.name,
            phone="",
            check_in_status=self.attendee.check_in_status,
            group_name=self.group.name,
            region_id_snapshot=self.group.region_id,
            region_name=self.group.region.name,
            division_id_snapshot=self.group.division_id,
            division_name=self.group.division.name,
        )
        from retreat.models import RetreatAttendance

        attendance = RetreatAttendance.objects.create(
            enrollment=enrollment,
            status=RetreatAttendance.Status.PRESENT,
        )
        RetreatChangeLog.objects.create(
            event=self.event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.ATTENDANCE,
            target_id=attendance.id,
            payload_before=None,
            payload_after={
                "id": attendance.id,
                "enrollment_id": enrollment.id,
                "attendee_id": self.attendee.id,
                "session_id": self.session.id,
                "status": "present",
                "note": "",
            },
            changed_by=self.leader,
        )
        other_enrollment = RetreatSessionAttendee.objects.create(
            session=self.session,
            source_attendee=self.other_attendee,
            source_group=self.other_group,
            name=self.other_attendee.name,
            check_in_status=self.other_attendee.check_in_status,
            group_name=self.other_group.name,
            region_id_snapshot=self.other_group.region_id,
            region_name=self.other_group.region.name,
            division_id_snapshot=self.other_group.division_id,
            division_name=self.other_group.division.name,
        )
        other_attendance = RetreatAttendance.objects.create(
            enrollment=other_enrollment,
            status=RetreatAttendance.Status.PRESENT,
        )
        RetreatChangeLog.objects.create(
            event=self.event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.ATTENDANCE,
            target_id=other_attendance.id,
            payload_after={
                "attendee_id": self.other_attendee.id,
                "session_id": self.session.id,
                "status": "present",
            },
            changed_by=self.leader,
        )

        self.client.force_authenticate(self.leader)
        r = self.client.get(self._url(self.attendee.id))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        sessions = data["attendance_history"]
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], self.session.id)
        self.assertEqual(len(sessions[0]["entries"]), 1)
        self.assertEqual(sessions[0]["entries"][0]["next_status"], "present")
        self.assertEqual(sessions[0]["current_status"], "present")
