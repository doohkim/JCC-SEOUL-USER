"""집회 최신 출석부 참석자(조+이름) 공개 API 테스트."""

from __future__ import annotations

from datetime import date
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
    RetreatSession,
    RetreatSessionAttendee,
)
from users.models import Division, Region


@override_settings(RETREAT="retreat-test-token")
class AttendanceNamesApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.region,
            code="attendance_names_div",
            name="청년부",
        )
        cls.event = RetreatEvent.objects.create(
            name="참석자 목록 집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.session = RetreatSession.objects.create(
            event=cls.event,
            name="저녁 집회",
            sequence=1,
        )
        cls.other_session = RetreatSession.objects.create(
            event=cls.event,
            name="새벽 집회",
            sequence=2,
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.region,
            division=cls.division,
            name="1조",
        )

        cls.attendee_present = RetreatAttendee.objects.create(
            group=cls.group,
            name="참석자",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.attendee_absent = RetreatAttendee.objects.create(
            group=cls.group,
            name="결석자",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.attendee_other_session = RetreatAttendee.objects.create(
            group=cls.group,
            name="다른세션참석자",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )

        cls.enrollment_present = cls._enroll(cls.session, cls.attendee_present)
        cls.enrollment_absent = cls._enroll(cls.session, cls.attendee_absent)
        cls.enrollment_other_session = cls._enroll(
            cls.other_session, cls.attendee_other_session
        )

        RetreatAttendance.objects.create(
            enrollment=cls.enrollment_present,
            status=RetreatAttendance.Status.PRESENT,
        )
        RetreatAttendance.objects.create(
            enrollment=cls.enrollment_absent,
            status=RetreatAttendance.Status.ABSENT,
        )
        RetreatAttendance.objects.create(
            enrollment=cls.enrollment_other_session,
            status=RetreatAttendance.Status.PRESENT,
        )

    @classmethod
    def _enroll(cls, session: RetreatSession, attendee: RetreatAttendee):
        group = attendee.group
        return RetreatSessionAttendee.objects.create(
            session=session,
            source_attendee=attendee,
            source_group=group,
            name=attendee.name,
            phone=attendee.phone,
            gender=attendee.gender,
            memo=attendee.memo,
            check_in_status=attendee.check_in_status,
            group_name=group.name,
            region_id_snapshot=group.region_id,
            region_name=group.region.name,
            division_id_snapshot=group.division_id,
            division_name=group.division.name,
        )

    def setUp(self):
        self.client = APIClient()
        self.url = reverse(
            "api_retreat_event_attendance_names",
            args=[self.event.id],
        )

    def test_request_without_token_returns_401(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_request_with_invalid_token_returns_401(self):
        response = self.client.get(self.url, HTTP_X_RETREAT_TOKEN="invalid-token")

        self.assertEqual(response.status_code, 401)

    def test_valid_token_returns_present_names_only_from_latest_session(self):
        response = self.client.get(
            self.url,
            HTTP_X_RETREAT_TOKEN=settings.RETREAT,
        )

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("attendees", data)
        self.assertEqual(data.get("event_id"), self.event.id)
        self.assertEqual(data.get("session_id"), self.other_session.id)
        self.assertEqual(
            data["attendees"],
            [
                {
                    "group_name": "1조",
                    "name": "다른세션참석자",
                }
            ],
        )

    def test_server_token_missing_returns_401_instead_of_500(self):
        with override_settings(RETREAT=""):
            with mock.patch.object(settings, "secrets", None, create=True):
                response = self.client.get(
                    self.url,
                    HTTP_X_RETREAT_TOKEN="any-token",
                )
        self.assertEqual(response.status_code, 401)

    def test_event_without_session_returns_404(self):
        empty_event = RetreatEvent.objects.create(
            name="세션 없는 집회",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
        )
        url = reverse(
            "api_retreat_event_attendance_names",
            args=[empty_event.id],
        )
        response = self.client.get(
            url,
            HTTP_X_RETREAT_TOKEN=settings.RETREAT,
        )
        self.assertEqual(response.status_code, 404)
