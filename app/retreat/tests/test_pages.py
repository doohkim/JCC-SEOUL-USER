"""수련회 UI 페이지(템플릿) 권한 가드 회귀 테스트."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatSession,
)
from retreat.services.enrollment import close_session, snapshot_session_enrollments
from users.models import Division, Region, RoleLevel, UserDivisionTeam

User = get_user_model()


class _PageFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div_youth = Division.objects.create(
            region=cls.seoul, code="pg_seoul_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="2026 봄 수련회",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 3),
        )
        cls.session = RetreatSession.objects.create(
            event=cls.event, name="1일차 저녁", sequence=1
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_youth,
            name="1조",
        )

        cls.leader = User.objects.create_user(username="page_leader", password="x")
        UserDivisionTeam.objects.create(
            user=cls.leader, division=cls.div_youth, is_primary=True
        )
        RetreatGroupMembership.objects.create(user=cls.leader, group=cls.group)

        cls.stranger = User.objects.create_user(username="page_stranger", password="x")
        UserDivisionTeam.objects.create(
            user=cls.stranger, division=cls.div_youth, is_primary=True
        )

        cls.rl_president, _ = RoleLevel.objects.get_or_create(
            code="president", defaults={"name": "회장", "level": 80, "sort_order": 20}
        )
        cls.staff = User.objects.create_user(username="page_staff", password="x")
        cls.staff.role_level = cls.rl_president
        cls.staff.save()
        UserDivisionTeam.objects.create(
            user=cls.staff, division=cls.div_youth, is_primary=True
        )

        cls.rl_pastor, _ = RoleLevel.objects.get_or_create(
            code="pastor", defaults={"name": "목사", "level": 90, "sort_order": 5}
        )
        cls.pastor = User.objects.create_user(username="page_pastor", password="x")
        cls.pastor.role_level = cls.rl_pastor
        cls.pastor.save()

        cls.council = User.objects.create_user(username="page_council", password="x")
        UserDivisionTeam.objects.create(
            user=cls.council, division=cls.div_youth, is_primary=True
        )
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council,
            role=RetreatCouncilMembership.Role.CHAIRPERSON,
        )

        cls.superuser = User.objects.create_user(
            username="page_super",
            password="x",
            is_staff=True,
            is_superuser=True,
        )


class RetreatPageAccessTests(_PageFixture):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_home_requires_login(self):
        r = self.client.get(reverse("retreat_home"))
        # LoginRequiredMixin → 302 to login
        self.assertEqual(r.status_code, 302)

    def test_home_forbidden_for_stranger(self):
        self.client.force_login(self.stranger)
        r = self.client.get(reverse("retreat_home"))
        self.assertEqual(r.status_code, 403)

    def test_home_redirects_to_dashboard_when_single_event(self):
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_home"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/dashboard/", r.url)

    def test_dashboard_ok_for_leader(self):
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_dashboard", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)

    def test_rosters_ok_for_leader(self):
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_rosters", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)

    def test_rosters_has_no_create_or_lifecycle_buttons_for_council(self):
        # 출석부 만들기/마감/재오픈 UI는 관리-출석부에서만 노출되어야 한다.
        self.client.force_login(self.council)
        r = self.client.get(reverse("retreat_rosters", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "출석부 만들기")
        self.assertNotContains(r, "data-session-close")
        self.assertNotContains(r, "data-session-reopen")

    def test_rosters_has_no_create_or_lifecycle_buttons_for_superuser(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("retreat_rosters", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "출석부 만들기")
        self.assertNotContains(r, "data-session-close")
        self.assertNotContains(r, "data-session-reopen")

    def test_results_ok_for_leader(self):
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_results", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)

    def test_group_detail_forbidden_for_stranger(self):
        self.client.force_login(self.stranger)
        r = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 403)

    def test_group_detail_ok_for_leader(self):
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)

    def test_manage_groups_list_ok_for_leader(self):
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_group_manage_list", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "조 관리")
        self.assertContains(r, self.group.name)

    def test_manage_groups_list_forbidden_for_stranger(self):
        self.client.force_login(self.stranger)
        r = self.client.get(reverse("retreat_group_manage_list", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)

    def test_manage_group_detail_persists_due_transitions(self):
        """조 관리 상세 진입 시 입실 시각이 지난 입실전 조원을 DB에 입실로 저장한다."""
        now = timezone.now()
        attendee = RetreatAttendee.objects.create(
            group=self.group,
            name="자동입실",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            expected_check_in_at=now - timedelta(hours=1),
        )
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse("retreat_group_manage", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)
        attendee.refresh_from_db()
        self.assertEqual(
            attendee.check_in_status, RetreatAttendee.CheckInStatus.CHECKED_IN
        )
        self.assertIsNotNone(attendee.checked_in_at)

    def test_manage_group_detail_has_check_in_tab_and_stamps(self):
        RetreatAttendee.objects.create(group=self.group, name="입실표시")
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse("retreat_group_manage", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="retreatEventSwitcher"')
        self.assertContains(r, "구분")
        self.assertContains(r, "data-status-badge")
        self.assertContains(r, "jcc-retreat-checkInBadge")
        # 조장(can_mutate)은 예상 입·퇴실 시각을 리스트에서 인라인으로 입력할 수 있다.
        self.assertContains(r, 'data-expected-field="expected_check_in_at"')
        self.assertContains(r, 'data-expected-field="expected_check_out_at"')
        # 입·퇴실 상태 변경은 수정 모달에서 처리한다.
        self.assertContains(r, 'id="retreatAttCheckIn"')
        self.assertNotContains(r, "data-check-in-group")
        # 정렬 가능한 컬럼 헤더 노출.
        self.assertContains(r, 'data-sort-key="role"')
        # 실제 입·퇴실 시각 수정 권한은 여전히 없다.
        self.assertFalse(r.context["can_edit_timestamps"])

    def test_manage_group_detail_staff_can_edit_timestamps(self):
        RetreatAttendee.objects.create(group=self.group, name="시각수정")
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse("retreat_group_manage", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_edit_timestamps"])
        self.assertTrue(r.context["can_edit_attendee"])
        self.assertContains(r, "구분")
        self.assertContains(r, "jcc-retreat-modal--attendeeEdit")

    def test_group_detail_exposes_can_manage_sessions_and_hint(self):
        self.client.force_login(self.superuser)
        r = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="retreatAddHint"')
        self.assertContains(r, "canManageSessions: true")
        self.assertTrue(r.context["can_manage_sessions"])

    def test_group_detail_exposes_back_url_referer(self):
        self.client.force_login(self.leader)
        referer_path = reverse(
            "retreat_roster_check",
            args=[self.event.id, self.session.id, self.group.id],
        )
        referer = f"http://testserver{referer_path}"
        r = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id]),
            HTTP_REFERER=referer,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["back_url"], referer_path)
        self.assertContains(r, "관리 완료")
        self.assertContains(r, f'href="{referer_path}"')

    def test_group_detail_exposes_back_url_default(self):
        self.client.force_login(self.leader)
        default_url = reverse("retreat_rosters", args=[self.event.id])
        r = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id]),
        )
        self.assertEqual(r.context["back_url"], default_url)

        r2 = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id]),
            HTTP_REFERER="https://evil.example/retreat/1/rosters/",
        )
        self.assertEqual(r2.context["back_url"], default_url)

    def test_group_detail_has_gender_column_and_modal_field(self):
        RetreatAttendee.objects.create(
            group=self.group, name="성별표시", gender=RetreatAttendee.Gender.FEMALE
        )
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "jcc-retreat-attCol-gender")
        self.assertContains(r, 'id="retreatAttGender"')
        self.assertContains(r, "여성")

    def test_group_detail_honors_session_id_query_for_active_tab(self):
        other_session = RetreatSession.objects.create(
            event=self.event, name="다른 출석부", sequence=2
        )
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id])
            + f"?session_id={self.session.id}"
        )
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        selected_idx = html.index(f'data-session-id="{self.session.id}"')
        other_idx = html.index(f'data-session-id="{other_session.id}"')
        selected_button = html.rfind("<button", 0, selected_idx)
        other_button = html.rfind("<button", 0, other_idx)
        self.assertIn("is-active", html[selected_button:selected_idx])
        self.assertNotIn("is-active", html[other_button:other_idx])

    def test_roster_check_manage_link_keeps_current_session(self):
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse(
                "retreat_roster_check",
                args=[self.event.id, self.session.id, self.group.id],
            )
        )
        self.assertEqual(r.status_code, 200)
        manage_url = reverse(
            "retreat_group_detail", args=[self.event.id, self.group.id]
        )
        self.assertContains(r, f'{manage_url}?session_id={self.session.id}')

    def test_event_switcher_dropdown_lists_accessible_events(self):
        other_event = RetreatEvent.objects.create(
            name="다른 행사",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 2),
        )
        other_group = RetreatGroup.objects.create(
            event=other_event,
            region=self.seoul,
            division=self.div_youth,
            name="조A",
        )
        RetreatGroupMembership.objects.create(user=self.leader, group=other_group)

        hidden_event = RetreatEvent.objects.create(
            name="비활성 행사",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 9, 2),
            is_active=False,
        )

        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_dashboard", args=[self.event.id]))

        self.assertEqual(r.status_code, 200)
        available_ids = [ev.id for ev in r.context["available_events"]]
        self.assertIn(self.event.id, available_ids)
        self.assertIn(other_event.id, available_ids)
        self.assertNotIn(hidden_event.id, available_ids)
        self.assertContains(r, 'id="retreatEventSwitcher"')
        self.assertContains(
            r, reverse("retreat_dashboard", args=[other_event.id])
        )

    def test_event_switcher_dropdown_options_match_current_tab(self):
        other_event = RetreatEvent.objects.create(
            name="다른 행사",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 2),
        )
        RetreatGroup.objects.create(
            event=other_event,
            region=self.seoul,
            division=self.div_youth,
            name="조A",
        )

        self.client.force_login(self.superuser)
        r = self.client.get(reverse("retreat_results", args=[self.event.id]))

        self.assertEqual(r.status_code, 200)
        self.assertContains(
            r, reverse("retreat_results", args=[other_event.id])
        )
        self.assertNotContains(
            r, reverse("retreat_dashboard", args=[other_event.id])
        )

    def test_roster_check_defaults_missing_attendance_to_absent(self):
        attendee = RetreatAttendee.objects.create(group=self.group, name="기본결석")
        snapshot_session_enrollments(self.session, actor=self.council)
        enrollment = self.session.enrollments.get(source_attendee=attendee)
        RetreatAttendance.objects.filter(enrollment=enrollment).delete()

        self.client.force_login(self.leader)
        r = self.client.get(
            reverse(
                "retreat_roster_check",
                args=[self.event.id, self.session.id, self.group.id],
            )
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.context["matrix"][enrollment.id], RetreatAttendance.Status.ABSENT
        )

    def test_group_detail_marks_post_closure_attendee_missing_in_closed_session(self):
        # 마감 이후에 추가된 라이브 조원은 마감 출석부에서 missing 으로 표시되어
        # JS 가 해당 마감 탭에서 행 자체를 숨길 수 있어야 한다.
        snapshot_session_enrollments(self.session, actor=self.council)
        close_session(self.session, actor=self.council)

        late_attendee = RetreatAttendee.objects.create(
            group=self.group, name="마감후추가"
        )

        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id])
        )
        self.assertEqual(response.status_code, 200)
        missing = response.context["missing_matrix"]
        self.assertTrue(missing[late_attendee.id][self.session.id])

    def test_group_detail_preserves_deleted_attendee_in_closed_session(self):
        attendee = RetreatAttendee.objects.create(
            group=self.group,
            name="삭제보존",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        snapshot_session_enrollments(self.session, actor=self.council)
        enrollment = self.session.enrollments.get(source_attendee=attendee)
        RetreatAttendance.objects.create(
            enrollment=enrollment,
            status=RetreatAttendance.Status.PRESENT,
        )
        close_session(self.session, actor=self.council)

        attendee.delete()

        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id])
        )

        self.assertEqual(response.status_code, 200)
        rows = list(response.context["attendees"])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row.is_snapshot_only)
        self.assertEqual(row.name, "삭제보존")
        self.assertEqual(
            response.context["matrix"][row.row_key][self.session.id],
            RetreatAttendance.Status.PRESENT,
        )
        self.assertContains(response, "삭제보존")
        self.assertContains(response, 'data-row-snapshot="1"')
        self.assertContains(response, "data-edit")

    def test_admin_forbidden_for_leader_only(self):
        # 조장 자격만 있는 사용자는 admin 페이지 접근 불가.
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)

    def test_admin_forbidden_for_general_staff(self):
        # 일반 staff(부서장/간사·회장 직급 등)는 admin 차단 — 슈퍼유저/회장단/목사·전도사만 허용.
        self.client.force_login(self.staff)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)

    def test_admin_ok_for_pastor_readonly(self):
        # 목사/전도사는 접근 가능하지만 출석부 만들기 버튼은 보이지 않음.
        self.client.force_login(self.pastor)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context["can_manage_sessions"])
        self.assertNotContains(r, "출석부 만들기")

    def test_admin_ok_for_council_with_create_button(self):
        self.client.force_login(self.council)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_sessions"])
        self.assertContains(r, "출석부 만들기")

    def test_admin_ok_for_superuser_with_create_button(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_manage_sessions"])
        self.assertContains(r, "출석부 만들기")

    def test_admin_default_tab_is_sessions(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.context["active_tab"], "sessions")
        self.assertIn(self.session, list(r.context["sessions"]))
        # 출석부 탭이 기본이라 조 rows 는 비어 있다.
        self.assertEqual(r.context["rows"], [])

    def test_admin_groups_tab_renders_rows(self):
        self.client.force_login(self.superuser)
        r = self.client.get(
            reverse("retreat_admin", args=[self.event.id]) + "?tab=groups"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["active_tab"], "groups")
        row_groups = [row["group"].id for row in r.context["rows"]]
        self.assertIn(self.group.id, row_groups)

    def test_admin_changelog_tab_returns_entries_context(self):
        self.client.force_login(self.superuser)
        r = self.client.get(
            reverse("retreat_admin", args=[self.event.id]) + "?tab=changelog"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["active_tab"], "changelog")
        self.assertIn("changelog_entries", r.context)

    def test_admin_pastor_sessions_tab_no_create_button(self):
        # 목사/전도사는 기본 sessions 탭에서도 read-only — 만들기 버튼이 없다.
        self.client.force_login(self.pastor)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["active_tab"], "sessions")
        self.assertFalse(r.context["can_manage_sessions"])
        self.assertNotContains(r, "출석부 만들기")

    def test_admin_create_modal_exposes_extended_fields(self):
        # 회장단/슈퍼유저 모달에 행사·상태·마감일시 필드가 함께 노출된다.
        self.client.force_login(self.council)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="rosterEvent"')
        self.assertContains(r, 'id="rosterStatus"')
        self.assertContains(r, 'id="rosterClosedAt"')
        # creatable_events에 본인이 회장단인 행사가 들어 있다.
        self.assertIn(
            self.event.id,
            [e.id for e in r.context["creatable_events"]],
        )


class CanAccessRetreatTabFilterTests(_PageFixture):
    """`{% load permission_tags %}` 필터 단위."""

    def _render(self, user):
        t = Template(
            "{% load permission_tags %}{{ u|can_access_retreat_tab|yesno:'1,0' }}"
        )
        return t.render(Context({"u": user})).strip()

    def test_leader_shows_tab(self):
        self.assertEqual(self._render(self.leader), "1")

    def test_staff_shows_tab(self):
        self.assertEqual(self._render(self.staff), "1")

    def test_stranger_does_not_show_tab(self):
        self.assertEqual(self._render(self.stranger), "0")

    def test_superuser_shows_tab(self):
        self.assertEqual(self._render(self.superuser), "1")
