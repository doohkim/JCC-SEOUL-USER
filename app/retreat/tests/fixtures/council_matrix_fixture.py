"""수련회 운영진 8역할 권한 매트릭스 공통 픽스처."""

from __future__ import annotations

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from retreat.models import (
    Lodging,
    LodgingRoom,
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatPickup,
    RetreatTimetableEntry,
)
from users.models import Division, Region, UserDivisionTeam

User = get_user_model()


def matrix_train_time(hour: int, minute: int = 0):
    return timezone.make_aware(datetime(2026, 8, 1, hour, minute))


class CouncilMatrixFixture(TestCase):
    """청년부 집회 + 서울/인천 조, 조원·픽업·숙소 샘플 데이터."""

    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.incheon = Region.objects.get(code="incheon")
        cls.div_seoul = Division.objects.create(
            region=cls.seoul, code="cm_seoul_y", name="서울청년"
        )
        cls.div_incheon = Division.objects.create(
            region=cls.incheon, code="cm_ic_y", name="인천청년"
        )

        cls.event = RetreatEvent.objects.create(
            name="2026년 청년부 수련회",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.other_event = RetreatEvent.objects.create(
            name="2026년 중고등부 수련회",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
        )

        cls.group_seoul = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_seoul,
            name="서울1조",
        )
        cls.group_incheon = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.incheon,
            division=cls.div_incheon,
            name="인천1조",
        )

        cls.pending = RetreatAttendee.objects.create(
            group=cls.group_seoul, name="입실전"
        )
        cls.checked_in = RetreatAttendee.objects.create(
            group=cls.group_seoul,
            name="입실중",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        cls.checked_out = RetreatAttendee.objects.create(
            group=cls.group_incheon,
            name="퇴실자",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )

        cls.link_user = User.objects.create_user(username="cm_link_target", password="x")

        cls.lodging = Lodging.objects.create(event=cls.event, name="본관")
        cls.room = LodgingRoom.objects.create(
            lodging=cls.lodging,
            number="101",
            capacity=4,
            region=cls.seoul,
            division=cls.div_seoul,
        )

        cls.arrival_pickup = RetreatPickup.objects.create(
            event=cls.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=cls.group_seoul,
            name="입실전",
            region=cls.seoul,
            division=cls.div_seoul,
            train_time=matrix_train_time(10),
            boarding_place="서울역",
            contact="010-1111-2222",
        )
        cls.departure_pickup = RetreatPickup.objects.create(
            event=cls.event,
            direction=RetreatPickup.Direction.DEPARTURE,
            number=1,
            group=cls.group_seoul,
            name="입실중",
            region=cls.seoul,
            division=cls.div_seoul,
            train_time=matrix_train_time(19),
            boarding_place="서울역",
            contact="010-3333-4444",
        )
        cls.incheon_arrival_pickup = RetreatPickup.objects.create(
            event=cls.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=2,
            group=cls.group_incheon,
            name="인천입실전",
            region=cls.incheon,
            division=cls.div_incheon,
            train_time=matrix_train_time(11),
            boarding_place="인천역",
            contact="010-5555-6666",
        )

        cls.timetable_entry = RetreatTimetableEntry.objects.create(
            event=cls.event,
            day=date(2026, 8, 1),
            start_time="09:00",
            title="개회",
        )

        cls.superuser = User.objects.create_superuser(
            username="cm_superuser", password="x"
        )
        cls.event_admin = cls._council_user(
            "cm_event_admin", RetreatCouncilMembership.Role.EVENT_ADMIN
        )
        cls.event_observer = cls._council_user(
            "cm_event_observer", RetreatCouncilMembership.Role.EVENT_OBSERVER
        )
        cls.region_admin = cls._council_user(
            "cm_region_admin",
            RetreatCouncilMembership.Role.REGION_ADMIN,
            region=cls.seoul,
        )
        cls.region_observer = cls._council_user(
            "cm_region_observer",
            RetreatCouncilMembership.Role.REGION_OBSERVER,
            region=cls.seoul,
        )
        cls.division_admin = cls._council_user(
            "cm_division_admin",
            RetreatCouncilMembership.Role.DIVISION_ADMIN,
            division=cls.div_seoul,
        )
        cls.division_observer = cls._council_user(
            "cm_division_observer",
            RetreatCouncilMembership.Role.DIVISION_OBSERVER,
            division=cls.div_seoul,
        )
        cls.pickup_observer = cls._council_user(
            "cm_pickup_observer", RetreatCouncilMembership.Role.PICKUP_OBSERVER
        )

    @classmethod
    def _council_user(cls, username: str, role: str, **scope) -> User:
        user = User.objects.create_user(username=username, password="x")
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=user,
            role=role,
            **scope,
        )
        return user

    def auth_as(self, user):
        self.api = APIClient()
        self.page = Client()
        self.api.force_authenticate(user)
        self.page.force_login(user)
        self.user = user

    def pickup_post_payload(
        self,
        *,
        direction: str = "arrival",
        name: str = "입실전",
        group=None,
        region=None,
        division=None,
    ):
        group = group or self.group_seoul
        region = region or group.region
        division = division or group.division
        return {
            "direction": direction,
            "name": name,
            "group": group.id,
            "region": region.id,
            "division": division.id,
            "train_time": "2026-08-01T12:00:00+09:00",
            "boarding_place": "역",
            "contact": "01012345678",
        }
