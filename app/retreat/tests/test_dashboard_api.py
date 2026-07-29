"""대시보드·결과 API 집계 테스트."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from retreat.models import (
    RetreatAttendee,
    RetreatAttendance,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatGroupScope,
    RetreatPickup,
    RetreatSession,
    RetreatSessionAttendee,
    RetreatTravelPreset,
)
from users.models import (
    Division,
    PastoralDivisionAssignment,
    Region,
    RoleLevel,
    UserDivisionTeam,
)

User = get_user_model()


class RetreatDashboardApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="dash_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="대시보드 테스트",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 2),
        )
        cls.session = RetreatSession.objects.create(
            event=cls.event, name="입실", sequence=1
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.attendee = RetreatAttendee.objects.create(group=cls.group, name="홍길동")
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
        RetreatAttendance.objects.create(
            enrollment=cls.enrollment,
            status=RetreatAttendance.Status.PRESENT,
        )
        cls.leader = User.objects.create_user(username="dash_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

    def setUp(self):
        self.client = APIClient()

    def test_dashboard_realtime_counts(self):
        # 입실 시각이 지나고 퇴실 시각은 미설정 → 현재 입실 상태로 집계.
        self.attendee.expected_check_in_at = timezone.now() - timedelta(minutes=10)
        self.attendee.save(update_fields=["expected_check_in_at"])
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["by_group"]), 1)
        self.assertEqual(data["by_group"][0]["checked_in"], 1)
        self.assertEqual(data["by_group"][0]["attended"], 1)
        self.assertEqual(data["grand_total"]["attended"], 1)
        self.assertEqual(data["grand_total"]["checked_in"], 1)
        # 1시간 단위 추이에 입실 1건 집계.
        self.assertEqual(len(data["hourly"]), 1)
        self.assertEqual(data["hourly"][0]["checked_in"], 1)

    def test_dashboard_gender_counts_by_division(self):
        """참석자 명단 gender 기준 부서별 남/여/미지정 집계."""
        self.attendee.gender = RetreatAttendee.Gender.MALE
        self.attendee.save(update_fields=["gender"])
        RetreatAttendee.objects.create(
            group=self.group,
            name="김영희",
            gender=RetreatAttendee.Gender.FEMALE,
        )
        RetreatAttendee.objects.create(
            group=self.group,
            name="미지정자",
            gender="",
        )
        # 불참은 성별 집계에서 제외
        RetreatAttendee.objects.create(
            group=self.group,
            name="불참남",
            gender=RetreatAttendee.Gender.MALE,
            participation_status=RetreatAttendee.ParticipationStatus.ABSENT,
        )

        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()

        self.assertEqual(data["by_group"][0]["male"], 1)
        self.assertEqual(data["by_group"][0]["female"], 1)
        self.assertEqual(data["by_group"][0]["gender_unknown"], 1)
        self.assertEqual(data["by_group"][0]["total"], 3)

        self.assertEqual(len(data["by_division"]), 1)
        div = data["by_division"][0]
        self.assertEqual(div["male"], 1)
        self.assertEqual(div["female"], 1)
        self.assertEqual(div["gender_unknown"], 1)
        self.assertEqual(div["total"], 3)

        self.assertEqual(data["grand_total"]["male"], 1)
        self.assertEqual(data["grand_total"]["female"], 1)
        self.assertEqual(data["grand_total"]["gender_unknown"], 1)
        self.assertEqual(data["grand_total"]["total"], 3)

    def test_dashboard_travel_wave_counts(self):
        """입·퇴실 예정 시각을 교통 프리셋 웨이브에 매칭해 집계한다."""
        tz = timezone.get_current_timezone()
        from datetime import datetime

        main_at = timezone.make_aware(datetime(2026, 7, 30, 10, 0), tz)
        bus_at = timezone.make_aware(datetime(2026, 8, 1, 13, 0), tz)
        arrival = RetreatTravelPreset.objects.create(
            event=self.event,
            direction=RetreatTravelPreset.Direction.ARRIVAL,
            code="main",
            label="7/30 본진",
            occurs_at=main_at,
            sort_order=10,
        )
        arrival.divisions.set([self.div])
        departure = RetreatTravelPreset.objects.create(
            event=self.event,
            direction=RetreatTravelPreset.Direction.DEPARTURE,
            code="bus_801",
            label="8/1 버스",
            occurs_at=bus_at,
            sort_order=10,
        )
        departure.divisions.set([self.div])
        RetreatTravelPreset.objects.create(
            event=self.event,
            direction=RetreatTravelPreset.Direction.ARRIVAL,
            code="own_car",
            label="자차",
            occurs_at=None,
            sort_order=20,
        )

        self.attendee.expected_check_in_at = main_at
        self.attendee.expected_check_out_at = bus_at
        self.attendee.save(
            update_fields=["expected_check_in_at", "expected_check_out_at"]
        )
        other = RetreatAttendee.objects.create(
            group=self.group,
            name="직접입력",
            expected_check_in_at=timezone.make_aware(datetime(2026, 7, 30, 15, 30), tz),
        )
        unset = RetreatAttendee.objects.create(group=self.group, name="미설정")

        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        travel = data["travel"]
        self.assertTrue(travel["has_presets"])
        arrival_by_label = {r["label"]: r["count"] for r in travel["arrival"]}
        self.assertEqual(arrival_by_label["7/30 본진"], 1)
        self.assertEqual(arrival_by_label["자차"], 1)
        self.assertEqual(arrival_by_label["미설정"], 1)
        departure_by_label = {r["label"]: r["count"] for r in travel["departure"]}
        self.assertEqual(departure_by_label["8/1 버스"], 1)
        # 나머지 2명은 퇴실 미설정
        self.assertEqual(departure_by_label["미설정"], 2)

        by_group = travel["by_group"]
        self.assertEqual(
            [c["label"] for c in by_group["arrival_columns"]],
            ["7/30 본진", "자차", "미설정"],
        )
        self.assertEqual(
            [c["label"] for c in by_group["departure_columns"]],
            ["8/1 버스", "자차", "미설정"],
        )
        self.assertEqual(len(by_group["rows"]), 1)
        g_row = by_group["rows"][0]
        self.assertEqual(g_row["group_id"], self.group.id)
        self.assertEqual(g_row["name"], "1조")
        self.assertEqual(g_row["arrival"], [1, 1, 1])
        self.assertEqual(g_row["arrival_total"], 3)
        self.assertEqual(g_row["departure"], [1, 0, 2])
        self.assertEqual(g_row["departure_total"], 3)

    def test_dashboard_travel_custom_flag_same_wave_time(self):
        """자차 명시 시 본진과 동일 시각이어도 자차 집계."""
        tz = timezone.get_current_timezone()
        from datetime import datetime

        main_at = timezone.make_aware(datetime(2026, 7, 30, 10, 0), tz)
        arrival = RetreatTravelPreset.objects.create(
            event=self.event,
            direction=RetreatTravelPreset.Direction.ARRIVAL,
            code="main",
            label="7/30 본진",
            occurs_at=main_at,
            sort_order=10,
        )
        arrival.divisions.set([self.div])
        self.attendee.expected_check_in_at = main_at
        self.attendee.arrival_travel_is_custom = True
        self.attendee.save(
            update_fields=["expected_check_in_at", "arrival_travel_is_custom"]
        )
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        travel = self.client.get(url).json()["travel"]
        arrival_by_label = {r["label"]: r["count"] for r in travel["arrival"]}
        self.assertEqual(arrival_by_label.get("7/30 본진", 0), 0)
        self.assertEqual(arrival_by_label["자차"], 1)

    def test_dashboard_status_is_time_based(self):
        """저장된 check_in_status 와 무관하게 입실/퇴실 시각으로 상태를 계산한다."""
        now = timezone.now()
        # 입실 시각이 미래 → 저장 상태가 입실이어도 입실전으로 집계.
        self.attendee.check_in_status = RetreatAttendee.CheckInStatus.CHECKED_IN
        self.attendee.expected_check_in_at = now + timedelta(hours=1)
        self.attendee.save(update_fields=["check_in_status", "expected_check_in_at"])
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["grand_total"]["pending"], 1)
        self.assertEqual(data["grand_total"]["checked_in"], 0)

        # 퇴실 시각까지 지나면 퇴실로 집계되며 참석(입실+퇴실)에는 포함.
        self.attendee.expected_check_in_at = now - timedelta(hours=2)
        self.attendee.expected_check_out_at = now - timedelta(minutes=5)
        self.attendee.save(
            update_fields=["expected_check_in_at", "expected_check_out_at"]
        )
        data = self.client.get(url).json()
        self.assertEqual(data["grand_total"]["checked_out"], 1)
        self.assertEqual(data["grand_total"]["checked_in"], 0)
        self.assertEqual(data["grand_total"]["attended"], 1)
        # 시각이 전혀 없으면 입실전.
        self.attendee.expected_check_in_at = None
        self.attendee.expected_check_out_at = None
        self.attendee.save(
            update_fields=["expected_check_in_at", "expected_check_out_at"]
        )
        data = self.client.get(url).json()
        self.assertEqual(data["grand_total"]["pending"], 1)
        self.assertEqual(data["grand_total"]["attended"], 0)

    def test_dashboard_reports_due_transition_without_writing(self):
        """대시보드는 유효 상태를 집계하되 조회 요청에서 DB를 변경하지 않는다."""
        now = timezone.now()
        self.attendee.check_in_status = RetreatAttendee.CheckInStatus.PENDING
        self.attendee.expected_check_in_at = now - timedelta(hours=1)
        self.attendee.save(update_fields=["check_in_status", "expected_check_in_at"])
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["grand_total"]["checked_in"], 1)
        self.attendee.refresh_from_db()
        self.assertEqual(
            self.attendee.check_in_status, RetreatAttendee.CheckInStatus.PENDING
        )
        self.assertIsNone(self.attendee.checked_in_at)

    def test_lodging_unassigned_counts_eligible_only(self):
        """미배정 카드는 숙박 대상(입실 예정·퇴실 제외)만 집계한다."""
        now = timezone.now()
        RetreatAttendee.objects.create(
            group=self.group,
            name="숙박미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        RetreatAttendee.objects.create(
            group=self.group,
            name="입실시각없음",
        )
        RetreatAttendee.objects.create(
            group=self.group,
            name="퇴실완료",
            expected_check_in_at=now - timedelta(days=1),
            expected_check_out_at=now - timedelta(hours=1),
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["lodging_unassigned"], 1)

    def test_lodging_unassigned_leader_sees_own_group_only(self):
        """조장은 본인 조 숙박 미배정 인원만 집계한다."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        RetreatAttendee.objects.create(
            group=self.group,
            name="우리조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        RetreatAttendee.objects.create(
            group=other_group,
            name="다른조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["lodging_unassigned"], 1)

    def test_lodging_unassigned_staff_sees_all_groups(self):
        """회장단은 집회 전체 조 숙박 미배정 인원을 집계한다."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        RetreatAttendee.objects.create(
            group=self.group,
            name="1조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        RetreatAttendee.objects.create(
            group=other_group,
            name="2조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        staff = User.objects.create_user(username="dash_lodging_council", password="x")
        RetreatCouncilMembership.objects.create(user=staff, event=self.event)
        self.client.force_authenticate(staff)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["lodging_unassigned"], 2)

    def test_multi_scope_group_counts_once_in_by_division(self):
        """다스코프 조는 지역 행마다 인원을 복제하지 않고, 동일 스코프면 한 행으로 합친다."""
        daegu = Region.objects.create(code="dash_daegu", name="대구", sort_order=40)
        daejeon = Region.objects.create(code="dash_daejeon", name="대전", sort_order=41)
        sejong = Region.objects.create(code="dash_sejong", name="세종", sort_order=42)
        div_daegu = Division.objects.create(
            region=daegu, code="dash_daegu_youth", name="청년부"
        )
        div_daejeon = Division.objects.create(
            region=daejeon, code="dash_daejeon_youth", name="청년부"
        )
        div_sejong = Division.objects.create(
            region=sejong, code="dash_sejong_youth", name="청년부"
        )
        for order, name in ((17, "17조"), (18, "18조")):
            group = RetreatGroup.objects.create(
                event=self.event,
                region=daegu,
                division=div_daegu,
                name=name,
                order=order,
            )
            RetreatGroupScope.objects.create(
                group=group, region=daejeon, division=div_daejeon
            )
            RetreatGroupScope.objects.create(
                group=group, region=sejong, division=div_sejong
            )
            RetreatAttendee.objects.create(
                group=group,
                name=f"{name}원",
                expected_check_in_at=timezone.now() + timedelta(hours=2),
            )
        staff = User.objects.create_user(
            username="dash_multi_scope_admin", password="x"
        )
        RetreatCouncilMembership.objects.create(
            user=staff,
            event=self.event,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )
        self.client.force_authenticate(staff)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()

        multi_rows = [
            row
            for row in data["by_division"]
            if "17" in str(row.get("group_range") or "")
            or "18" in str(row.get("group_range") or "")
        ]
        self.assertEqual(len(multi_rows), 1)
        self.assertEqual(multi_rows[0]["group_range"], "17~18조")
        self.assertEqual(multi_rows[0]["pending"], 2)
        self.assertIn("대구", multi_rows[0]["region"])
        self.assertIn("대전", multi_rows[0]["region"])
        self.assertIn("세종", multi_rows[0]["region"])
        self.assertEqual(multi_rows[0].get("division") or "", "")

    def test_same_region_multi_division_scopes_merge_to_one_row(self):
        """인천 청년부+대학부처럼 같은 지역 다부서 스코프 조들은 1행으로 합친다."""
        incheon = Region.objects.create(code="dash_incheon", name="인천", sort_order=50)
        div_youth = Division.objects.create(
            region=incheon, code="dash_icn_youth", name="청년부"
        )
        div_univ = Division.objects.create(
            region=incheon, code="dash_icn_univ", name="대학부"
        )
        for order in (9, 10):
            group = RetreatGroup.objects.create(
                event=self.event,
                region=incheon,
                division=div_youth,
                name=f"{order}조",
                order=order,
            )
            RetreatGroupScope.objects.create(
                group=group, region=incheon, division=div_univ
            )
            RetreatAttendee.objects.create(
                group=group,
                name=f"{order}조원",
                expected_check_in_at=timezone.now() + timedelta(hours=2),
            )
        staff = User.objects.create_user(username="dash_incheon_merge", password="x")
        RetreatCouncilMembership.objects.create(
            user=staff,
            event=self.event,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )
        self.client.force_authenticate(staff)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        rows = [
            row for row in data["by_division"] if "인천" in str(row.get("region") or "")
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["group_range"], "9~10조")
        self.assertEqual(rows[0]["pending"], 2)
        self.assertEqual(rows[0]["region"], "인천 · 청년부·대학부")
        self.assertEqual(rows[0].get("division") or "", "")

    def test_results_grand_total(self):
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_results", args=[self.event.id])
        r = self.client.get(url, {"session_id": self.session.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["grand_total"], 1)

    def test_results_analytics_matrix(self):
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_results_analytics", args=[self.event.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["groups"]), 1)
        self.assertEqual(len(data["sessions"]), 1)
        sess = data["sessions"][0]
        self.assertEqual(sess["total_present"], 1)
        self.assertEqual(sess["total_registered"], 1)
        gid = str(self.group.id)
        self.assertEqual(sess["groups"][gid]["present"], 1)
        self.assertEqual(sess["groups"][gid]["registered"], 1)

    def test_group_board_restricts_non_staff_to_own_region(self):
        """일반 사용자(조장)는 조 참석현황 보드에서 본인 소속 지역 조만 본다."""
        busan = Region.objects.create(code="busan_dash", name="부산", sort_order=99)
        busan_div = Division.objects.create(
            region=busan, code="dash_busan_youth", name="부산청년부"
        )
        RetreatGroup.objects.create(
            event=self.event, region=busan, division=busan_div, name="부산1조"
        )
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_group_board", args=[self.event.id])
        data = self.client.get(url).json()
        regions = {g["region"] for g in data["groups"]}
        self.assertEqual(regions, {self.seoul.name})
        self.assertNotIn(busan.name, regions)

    def test_group_board_includes_participation_and_absent_for_filtering(self):
        """조 참석현황 필터용 참석·불참 상태와 6종 요약 집계를 제공한다."""
        RetreatAttendee.objects.create(
            group=self.group,
            name="보드불참자",
            participation_status=RetreatAttendee.ParticipationStatus.ABSENT,
        )
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_group_board", args=[self.event.id])
        data = self.client.get(url).json()
        group = next(row for row in data["groups"] if row["group_id"] == self.group.id)
        absent = next(
            member for member in group["members"] if member["name"] == "보드불참자"
        )
        self.assertEqual(absent["participation_status"], "absent")
        self.assertEqual(absent["participation_label"], "불참")
        self.assertEqual(absent["status"], "absent")
        self.assertEqual(group["absent"], 1)
        self.assertEqual(group["roster_total"], group["participating"] + 1)
        self.assertEqual(data["grand_total"]["absent"], 1)

    def test_group_board_includes_arrival_and_departure_travel_filters(self):
        """조별 현황의 입회·출회 교통 필터 선택지와 조원 분류값을 제공한다."""
        tz = timezone.get_current_timezone()
        arrival_at = timezone.make_aware(datetime(2026, 6, 1, 10, 0), tz)
        departure_at = timezone.make_aware(datetime(2026, 6, 3, 13, 0), tz)
        arrival = RetreatTravelPreset.objects.create(
            event=self.event,
            direction=RetreatTravelPreset.Direction.ARRIVAL,
            code="board_main",
            label="본진",
            occurs_at=arrival_at,
        )
        departure = RetreatTravelPreset.objects.create(
            event=self.event,
            direction=RetreatTravelPreset.Direction.DEPARTURE,
            code="board_bus",
            label="버스",
            occurs_at=departure_at,
        )
        self.attendee.expected_check_in_at = arrival_at
        self.attendee.expected_check_out_at = departure_at
        self.attendee.save(
            update_fields=["expected_check_in_at", "expected_check_out_at"]
        )

        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_group_board", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(
            [row["value"] for row in data["travel_filters"]["arrival"]],
            [str(arrival.id), "__custom__", "__unset__"],
        )
        self.assertEqual(
            [row["value"] for row in data["travel_filters"]["departure"]],
            [str(departure.id), "__custom__", "__unset__"],
        )
        group = next(row for row in data["groups"] if row["group_id"] == self.group.id)
        member = next(
            row for row in group["members"] if row["name"] == self.attendee.name
        )
        self.assertEqual(member["arrival_travel"], str(arrival.id))
        self.assertEqual(member["departure_travel"], str(departure.id))

    def test_group_board_shows_all_regions_for_staff(self):
        """수련회 회장단은 전체 지역 조를 본다."""
        busan = Region.objects.create(code="busan_staff", name="부산", sort_order=99)
        busan_div = Division.objects.create(
            region=busan, code="staff_busan_youth", name="부산청년부"
        )
        RetreatGroup.objects.create(
            event=self.event, region=busan, division=busan_div, name="부산1조"
        )
        staff = User.objects.create_user(username="dash_staff", password="x")
        UserDivisionTeam.objects.create(user=staff, division=self.div, is_primary=True)
        RetreatCouncilMembership.objects.create(user=staff, event=self.event)
        self.client.force_authenticate(staff)
        url = reverse("api_retreat_event_group_board", args=[self.event.id])
        data = self.client.get(url).json()
        regions = {g["region"] for g in data["groups"]}
        self.assertIn(self.seoul.name, regions)
        self.assertIn(busan.name, regions)

    def test_car_today_leader_sees_own_group_only(self):
        """조장은 당일 본인 조 픽업 인원만 집계한다."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="우리조원",
            region=self.seoul,
            division=self.div,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=2,
            group=other_group,
            name="다른조원",
            region=self.seoul,
            division=self.div,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["car_today"], 1)

    def test_car_today_staff_sees_all_groups(self):
        """회장단은 당일 전체 조 픽업 인원을 집계한다."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="1조원",
            region=self.seoul,
            division=self.div,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=2,
            group=other_group,
            name="2조원",
            region=self.seoul,
            division=self.div,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        staff = User.objects.create_user(username="dash_council", password="x")
        RetreatCouncilMembership.objects.create(user=staff, event=self.event)
        self.client.force_authenticate(staff)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["car_today"], 2)

    def test_car_today_excludes_absent_and_other_dates(self):
        """불참 조원·다른 날짜 픽업은 당일 차량 지원 집계에서 제외."""
        now = timezone.now()
        RetreatAttendee.objects.create(
            group=self.group,
            name="불참픽업",
            participation_status=RetreatAttendee.ParticipationStatus.ABSENT,
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="참석픽업",
            region=self.seoul,
            division=self.div,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=2,
            group=self.group,
            name="불참픽업",
            region=self.seoul,
            division=self.div,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=3,
            group=self.group,
            name="어제픽업",
            region=self.seoul,
            division=self.div,
            train_time=now - timedelta(days=1),
            boarding_place="역",
            contact="010",
        )
        self.client.force_authenticate(self.leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["car_today"], 1)

    def test_lodging_unassigned_superuser_sees_all_groups(self):
        """슈퍼유저는 집회 전체 조 숙박 미배정 인원을 집계한다."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        RetreatAttendee.objects.create(
            group=self.group,
            name="1조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        RetreatAttendee.objects.create(
            group=other_group,
            name="2조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        superuser = User.objects.create_superuser(
            username="dash_superuser", password="x", email="su@test.local"
        )
        self.client.force_authenticate(superuser)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["lodging_unassigned"], 2)

    def test_lodging_unassigned_vice_leader_sees_own_group_only(self):
        """부조장은 본인 조 숙박 미배정 인원만 집계한다."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        RetreatAttendee.objects.create(
            group=self.group,
            name="우리조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        RetreatAttendee.objects.create(
            group=other_group,
            name="다른조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        vice_leader = User.objects.create_user(
            username="dash_vice_leader", password="x"
        )
        UserDivisionTeam.objects.create(
            user=vice_leader, division=self.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(
            user=vice_leader,
            group=self.group,
            role=RetreatGroupMembership.Role.VICE_LEADER,
        )
        self.client.force_authenticate(vice_leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["lodging_unassigned"], 1)

    def test_lodging_unassigned_council_leader_sees_all_groups(self):
        """회장단이면서 조장이면 집회 전체 조를 집계한다 (회장단 우선)."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        RetreatAttendee.objects.create(
            group=self.group,
            name="1조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        RetreatAttendee.objects.create(
            group=other_group,
            name="2조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        council_leader = User.objects.create_user(
            username="dash_council_leader", password="x"
        )
        RetreatCouncilMembership.objects.create(user=council_leader, event=self.event)
        RetreatGroupMembership.objects.create(user=council_leader, group=self.group)
        self.client.force_authenticate(council_leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["lodging_unassigned"], 2)

    def test_car_today_superuser_sees_all_groups(self):
        """슈퍼유저는 당일 전체 조 픽업 인원을 집계한다."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        for number, group, name in (
            (1, self.group, "1조원"),
            (2, other_group, "2조원"),
        ):
            RetreatPickup.objects.create(
                event=self.event,
                direction=RetreatPickup.Direction.ARRIVAL,
                number=number,
                group=group,
                name=name,
                region=self.seoul,
                division=self.div,
                train_time=now,
                boarding_place="역",
                contact="010",
            )
        superuser = User.objects.create_superuser(
            username="dash_car_superuser", password="x", email="car-su@test.local"
        )
        self.client.force_authenticate(superuser)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["car_today"], 2)

    def test_car_today_vice_leader_sees_own_group_only(self):
        """부조장은 당일 본인 조 픽업 인원만 집계한다."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="우리조원",
            region=self.seoul,
            division=self.div,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=2,
            group=other_group,
            name="다른조원",
            region=self.seoul,
            division=self.div,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        vice_leader = User.objects.create_user(
            username="dash_car_vice_leader", password="x"
        )
        UserDivisionTeam.objects.create(
            user=vice_leader, division=self.div, is_primary=True
        )
        RetreatGroupMembership.objects.create(
            user=vice_leader,
            group=self.group,
            role=RetreatGroupMembership.Role.VICE_LEADER,
        )
        self.client.force_authenticate(vice_leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["car_today"], 1)

    def test_car_today_council_leader_sees_all_groups(self):
        """회장단이면서 조장이면 당일 전체 조 픽업을 집계한다 (회장단 우선)."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        for number, group, name in (
            (1, self.group, "1조원"),
            (2, other_group, "2조원"),
        ):
            RetreatPickup.objects.create(
                event=self.event,
                direction=RetreatPickup.Direction.ARRIVAL,
                number=number,
                group=group,
                name=name,
                region=self.seoul,
                division=self.div,
                train_time=now,
                boarding_place="역",
                contact="010",
            )
        council_leader = User.objects.create_user(
            username="dash_car_council_leader", password="x"
        )
        RetreatCouncilMembership.objects.create(user=council_leader, event=self.event)
        RetreatGroupMembership.objects.create(user=council_leader, group=self.group)
        self.client.force_authenticate(council_leader)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(data["summary"]["car_today"], 2)

    def test_dashboard_page_summary_aligns_with_api_for_roles(self):
        """대시보드 페이지 isStaff·API summary가 역할별 집계 범위와 일치한다."""
        now = timezone.now()
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div,
            name="2조",
        )
        RetreatAttendee.objects.create(
            group=self.group,
            name="1조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        RetreatAttendee.objects.create(
            group=other_group,
            name="2조미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group,
            name="1조픽업",
            region=self.seoul,
            division=self.div,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=2,
            group=other_group,
            name="2조픽업",
            region=self.seoul,
            division=self.div,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        api_url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        page_url = reverse("retreat_dashboard", args=[self.event.id])

        self.client.force_login(self.leader)
        page = self.client.get(page_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "isStaff: false")
        self.assertContains(page, "canNavigateGroups: false")
        self.assertNotContains(
            page, f'href="{reverse("retreat_lodging_roster", args=[self.event.id])}'
        )
        summary = self.client.get(api_url).json()["summary"]
        self.assertEqual(summary["lodging_unassigned"], 1)
        self.assertEqual(summary["car_today"], 1)

        council = User.objects.create_user(username="dash_page_council", password="x")
        RetreatCouncilMembership.objects.create(user=council, event=self.event)
        self.client.force_login(council)
        page = self.client.get(page_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "isStaff: true")
        self.assertContains(page, "canNavigateGroups: true")
        self.assertContains(
            page, f'href="{reverse("retreat_lodging_roster", args=[self.event.id])}'
        )
        summary = self.client.get(api_url).json()["summary"]
        self.assertEqual(summary["lodging_unassigned"], 2)
        self.assertEqual(summary["car_today"], 2)


class RetreatDashboardPastoralScopeTests(APITestCase):
    """부서 관리자: 담당 부서 조만 대시보드에 집계."""

    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div_youth = Division.objects.create(
            region=cls.seoul, code="dash_past_youth", name="청년부"
        )
        cls.div_univ = Division.objects.create(
            region=cls.seoul, code="dash_past_univ", name="대학부"
        )
        cls.event = RetreatEvent.objects.create(
            name="부서 관리자 집계",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 2),
        )
        cls.group_youth = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_youth,
            name="청년1조",
        )
        cls.group_univ = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_univ,
            name="대학1조",
        )
        cls.division_admin = User.objects.create_user(
            username="dash_div_admin", password="x"
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.division_admin,
            role=RetreatCouncilMembership.Role.DIVISION_ADMIN,
            division=cls.div_youth,
        )

    def setUp(self):
        self.client = APIClient()

    def test_division_admin_dashboard_summary_scoped_to_assigned_division(self):
        now = timezone.now()
        RetreatAttendee.objects.create(
            group=self.group_youth,
            name="청년미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        RetreatAttendee.objects.create(
            group=self.group_univ,
            name="대학미배정",
            expected_check_in_at=now + timedelta(hours=2),
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            group=self.group_youth,
            name="청년픽업",
            region=self.seoul,
            division=self.div_youth,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        RetreatPickup.objects.create(
            event=self.event,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=2,
            group=self.group_univ,
            name="대학픽업",
            region=self.seoul,
            division=self.div_univ,
            train_time=now,
            boarding_place="역",
            contact="010",
        )
        self.client.force_authenticate(self.division_admin)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        self.assertEqual(len(data["by_group"]), 1)
        self.assertEqual(data["by_group"][0]["group_id"], self.group_youth.id)
        self.assertEqual(data["summary"]["lodging_unassigned"], 1)
        self.assertEqual(data["summary"]["car_today"], 1)

    def test_division_admin_group_board_excludes_other_division(self):
        self.client.force_authenticate(self.division_admin)
        url = reverse("api_retreat_event_group_board", args=[self.event.id])
        data = self.client.get(url).json()
        group_ids = {g["group_id"] for g in data["groups"]}
        self.assertEqual(group_ids, {self.group_youth.id})

    def test_division_admin_dashboard_includes_extra_scope_group(self):
        shared_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.div_univ,
            name="공유대학1조",
        )
        RetreatGroupScope.objects.create(
            group=shared_group,
            region=self.seoul,
            division=self.div_youth,
        )
        self.client.force_authenticate(self.division_admin)
        url = reverse("api_retreat_event_dashboard", args=[self.event.id])
        data = self.client.get(url).json()
        group_ids = {row["group_id"] for row in data["by_group"]}
        self.assertEqual(group_ids, {self.group_youth.id, shared_group.id})
        division_ids = {row["division_id"] for row in data["by_division"]}
        self.assertEqual(division_ids, {self.div_youth.id})
