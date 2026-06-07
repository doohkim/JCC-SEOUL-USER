"""세션별 일괄 출석 upsert 멱등성 테스트."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatSession,
    RetreatSessionAttendee,
)
from users.models import Division, Region, UserDivisionTeam

User = get_user_model()


URL = "/api/v1/retreat/attendance/bulk-upsert/"


class BulkUpsertTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.incheon, _ = Region.objects.get_or_create(
            code="incheon", defaults={"name": "인천", "sort_order": 20}
        )
        cls.div_seoul = Division.objects.create(
            region=cls.seoul, code="bk_seoul_youth", name="청년부"
        )
        cls.div_incheon = Division.objects.create(
            region=cls.incheon, code="bk_incheon_youth", name="청년부"
        )

        cls.event = RetreatEvent.objects.create(
            name="2026 여름",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.session = RetreatSession.objects.create(
            event=cls.event, name="1일차 저녁", sequence=1
        )
        cls.session_other_event = RetreatSession.objects.create(
            event=RetreatEvent.objects.create(
                name="다른 행사",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 2),
            ),
            name="아무 세션",
        )

        cls.group_seoul = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_seoul,
            name="1조",
        )
        cls.group_incheon = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.incheon,
            division=cls.div_incheon,
            name="인천 1조",
        )

        cls.leader = User.objects.create_user(username="bk_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div_seoul, is_primary=True
        )
        RetreatGroupMembership.objects.create(
            user=cls.leader, group=cls.group_seoul
        )

        # 기존 케이스는 입실 상태 가정 — 명시적으로 CHECKED_IN 지정.
        cls.att_a = RetreatAttendee.objects.create(
            group=cls.group_seoul,
            name="A",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.att_b = RetreatAttendee.objects.create(
            group=cls.group_seoul,
            name="B",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.att_incheon = RetreatAttendee.objects.create(
            group=cls.group_incheon,
            name="인천A",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.att_pending = RetreatAttendee.objects.create(
            group=cls.group_seoul,
            name="입실전C",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        cls.enroll_a = cls._enroll(cls.session, cls.att_a)
        cls.enroll_b = cls._enroll(cls.session, cls.att_b)
        cls.enroll_incheon = cls._enroll(cls.session, cls.att_incheon)
        cls.enroll_pending = cls._enroll(cls.session, cls.att_pending)

    @classmethod
    def _enroll(cls, session, attendee):
        group = attendee.group
        return RetreatSessionAttendee.objects.create(
            session=session,
            source_attendee=attendee,
            source_group=group,
            name=attendee.name,
            phone=attendee.phone,
            gender=attendee.gender,
            check_in_status=attendee.check_in_status,
            group_name=group.name,
            region_id_snapshot=group.region_id,
            region_name=group.region.name,
            division_id_snapshot=group.division_id,
            division_name=group.division.name,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.leader)

    def _payload(self, rows):
        return {"session_id": self.session.id, "rows": rows}

    def test_first_upsert_creates_rows(self):
        r = self.client.post(
            URL,
            self._payload(
                [
                    {"attendee_id": self.att_a.id, "status": "present"},
                    {"attendee_id": self.att_b.id, "status": "absent", "note": "결석"},
                ]
            ),
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body["created"], 2)
        self.assertEqual(body["updated"], 0)
        self.assertEqual(RetreatAttendance.objects.count(), 2)

    def test_second_upsert_is_idempotent(self):
        """동일 입력 재호출 → 행 수 동일, updated 카운트만 증가, 마지막 값 보장."""
        payload = self._payload(
            [
                {"attendee_id": self.att_a.id, "status": "present"},
                {"attendee_id": self.att_b.id, "status": "absent"},
            ]
        )
        self.client.post(URL, payload, format="json")
        r = self.client.post(URL, payload, format="json")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["created"], 0)
        self.assertEqual(body["updated"], 2)
        self.assertEqual(RetreatAttendance.objects.count(), 2)

    def test_status_change_overrides_previous(self):
        self.client.post(
            URL,
            self._payload([{"attendee_id": self.att_a.id, "status": "present"}]),
            format="json",
        )
        self.client.post(
            URL,
            self._payload(
                [
                    {
                        "attendee_id": self.att_a.id,
                        "status": "absent",
                        "note": "감기",
                    }
                ]
            ),
            format="json",
        )
        att = RetreatAttendance.objects.get(enrollment=self.enroll_a)
        self.assertEqual(att.status, "absent")
        self.assertEqual(att.note, "감기")
        self.assertEqual(att.checked_by, self.leader)

    def test_duplicate_attendee_id_rejected(self):
        r = self.client.post(
            URL,
            self._payload(
                [
                    {"attendee_id": self.att_a.id, "status": "present"},
                    {"attendee_id": self.att_a.id, "status": "absent"},
                ]
            ),
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(RetreatAttendance.objects.count(), 0)

    def test_attendee_from_other_event_rejected_and_rolled_back(self):
        # 다른 행사 세션에 우리 attendee 를 넣으면 400 (event 불일치).
        r = self.client.post(
            URL,
            {
                "session_id": self.session_other_event.id,
                "rows": [{"attendee_id": self.att_a.id, "status": "present"}],
            },
            format="json",
        )
        self.assertIn(r.status_code, (400, 403))
        self.assertEqual(RetreatAttendance.objects.count(), 0)

    def test_attendee_outside_visibility_rejected(self):
        # 우리 조장이 인천 조원을 우리 세션에 등록 시도 → 403, 전체 롤백.
        r = self.client.post(
            URL,
            self._payload(
                [
                    {"attendee_id": self.att_a.id, "status": "present"},
                    {"attendee_id": self.att_incheon.id, "status": "present"},
                ]
            ),
            format="json",
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(RetreatAttendance.objects.count(), 0)

    def test_pending_cannot_be_marked_present(self):
        """입실전 상태인 조원에게 '참석'을 보내면 400."""
        r = self.client.post(
            URL,
            self._payload(
                [{"attendee_id": self.att_pending.id, "status": "present"}]
            ),
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(RetreatAttendance.objects.count(), 0)

    def test_pending_cannot_be_marked_absent(self):
        """입실전 조원에게 '결석'도 설정 불가."""
        r = self.client.post(
            URL,
            self._payload(
                [{"attendee_id": self.att_pending.id, "status": "absent"}]
            ),
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(RetreatAttendance.objects.count(), 0)
