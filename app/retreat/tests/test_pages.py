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
from retreat.services.enrollment import snapshot_session_enrollments
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

    def test_home_redirects_to_dashboard_when_accessible_event(self):
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_home"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(f"/retreat/{self.event.id}/dashboard/", r.url)

    def test_home_redirects_to_most_recently_created_event(self):
        older = self.event
        newer = RetreatEvent.objects.create(
            name="2026 여름 수련회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        newer_group = RetreatGroup.objects.create(
            event=newer,
            region=self.seoul,
            division=self.div_youth,
            name="2조",
        )
        RetreatGroupMembership.objects.create(user=self.leader, group=newer_group)

        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_home"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(f"/retreat/{newer.id}/dashboard/", r.url)
        self.assertNotIn(f"/retreat/{older.id}/dashboard/", r.url)

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

    def test_group_detail_page_deprecated_returns_404(self):
        # 과거 출석부 탭 화면은 조 관리(retreat_group_manage)로 대체되어 404 를 반환한다.
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse("retreat_group_detail", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 404)

    def test_manage_groups_list_ok_for_leader(self):
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_group_manage_list", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "그룹")
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

    def test_manage_group_detail_leader_can_edit(self):
        RetreatAttendee.objects.create(group=self.group, name="입실표시")
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse("retreat_group_manage", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="retreatEventPicker"')
        self.assertContains(r, "역할")
        self.assertContains(r, "data-status-badge")
        self.assertContains(r, "jcc-retreat-checkInBadge")
        self.assertTrue(r.context["can_edit_attendee"])
        self.assertTrue(r.context["can_delete_attendee"])
        self.assertFalse(r.context["can_change_status"])
        self.assertContains(r, 'data-expected-field="expected_check_in_at"')
        self.assertContains(r, 'id="btnAddAttendee"')
        self.assertContains(r, "사용자 연동")
        self.assertNotContains(r, "읽기 전용")
        self.assertContains(r, 'data-sort-key="role"')

    def test_manage_group_detail_checked_out_has_profile_locked(self):
        RetreatAttendee.objects.create(
            group=self.group,
            name="퇴실조원",
            gender="male",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse("retreat_group_manage", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-profile-locked="true"')
        self.assertContains(r, 'data-expected-out-locked="true"')
        self.assertContains(r, ">보기</button>")

    def test_manage_group_detail_council_checked_out_expected_out_editable(self):
        RetreatAttendee.objects.create(
            group=self.group,
            name="퇴실조원",
            gender="male",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        self.client.force_login(self.council)
        r = self.client.get(
            reverse("retreat_group_manage", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-expected-out-locked="false"')
        self.assertNotContains(
            r,
            'aria-label="퇴실조원 퇴실 시각" disabled',
        )

    def test_manage_group_detail_council_can_edit_timestamps(self):
        RetreatAttendee.objects.create(group=self.group, name="시각수정")
        self.client.force_login(self.council)
        r = self.client.get(
            reverse("retreat_group_manage", args=[self.event.id, self.group.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["can_edit_attendee"])
        self.assertContains(r, "구분")
        self.assertContains(r, "jcc-retreat-modal--attendeeEdit")

    def test_roster_check_links_to_group_manage(self):
        # 출석체크 화면의 '조원 관리' 링크는 조 관리(retreat_group_manage)로 이동한다.
        self.client.force_login(self.leader)
        r = self.client.get(
            reverse(
                "retreat_roster_check",
                args=[self.event.id, self.session.id, self.group.id],
            )
        )
        self.assertEqual(r.status_code, 200)
        manage_url = reverse(
            "retreat_group_manage", args=[self.event.id, self.group.id]
        )
        self.assertContains(r, manage_url)

    def test_event_switcher_dropdown_lists_accessible_events(self):
        other_event = RetreatEvent.objects.create(
            name="다른 집회",
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
            name="비활성 집회",
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
            name="다른 집회",
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

    def test_admin_forbidden_for_leader_only(self):
        # 조장 자격만 있는 사용자는 admin 페이지 접근 불가.
        self.client.force_login(self.leader)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)

    def test_admin_forbidden_for_general_staff(self):
        # 부서 회장·부회장·총무 등 조직 직급은 admin 차단 — 슈퍼유저·수련회 회장단만 허용.
        self.client.force_login(self.staff)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)

    def test_admin_forbidden_for_pastor(self):
        self.client.force_login(self.pastor)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)

    def test_admin_changelog_forbidden_for_pastor(self):
        self.client.force_login(self.pastor)
        r = self.client.get(
            reverse("retreat_admin", args=[self.event.id]) + "?tab=changelog"
        )
        self.assertEqual(r.status_code, 403)

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

    def test_admin_pastor_forbidden_on_sessions_tab(self):
        self.client.force_login(self.pastor)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)

    def test_admin_create_modal_exposes_extended_fields(self):
        # 회장단/슈퍼유저 모달에 집회·상태·마감일시 필드가 함께 노출된다.
        self.client.force_login(self.council)
        r = self.client.get(reverse("retreat_admin", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="rosterEvent"')
        self.assertContains(r, 'id="rosterStatus"')
        self.assertContains(r, 'id="rosterClosedAt"')
        # creatable_events에 본인이 회장단인 집회가 들어 있다.
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

    def test_org_president_does_not_show_tab(self):
        """부서 회장 직급만으로는 수련회 탭 미노출."""
        self.assertEqual(self._render(self.staff), "0")

    def test_stranger_does_not_show_tab(self):
        self.assertEqual(self._render(self.stranger), "0")

    def test_superuser_shows_tab(self):
        self.assertEqual(self._render(self.superuser), "1")
