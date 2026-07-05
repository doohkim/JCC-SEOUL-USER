"""운영진 참가 신청 — 모델·서비스·API·페이지."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from retreat.models import (
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatGroupScope,
    RetreatStaffApplication,
    StaffApplicationTrack,
)
from retreat.services.staff_application import (
    apply_staff_application,
    delete_staff_application_if_unassigned,
    eligible_groups_for_member,
    event_staff_status,
    member_can_apply_to_event,
    reject_staff_application,
)
from users.mixins import ensure_user_profile
from users.models import Division, Region, RoleLevel, UserDivisionTeam, UserProfile

User = get_user_model()


class StaffApplicationFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div_youth = Division.objects.create(
            region=cls.seoul, code="sa_seoul_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="2027 여름 수련회",
            start_date=date(2027, 7, 1),
            end_date=date(2027, 7, 3),
            staff_applications_open=True,
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_youth,
            name="1조",
            order=1,
        )

        cls.applicant = User.objects.create_user(
            username="staff_applicant", password="x", email="applicant@example.com"
        )
        UserDivisionTeam.objects.create(
            user=cls.applicant, division=cls.div_youth, is_primary=True
        )
        profile = ensure_user_profile(cls.applicant)
        profile.real_name = "신청자"
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.save()

        cls.pastor = User.objects.create_user(username="staff_pastor", password="x")
        cls.rl_pastor, _ = RoleLevel.objects.get_or_create(
            code="pastor", defaults={"name": "목사", "level": 90, "sort_order": 5}
        )
        cls.pastor.role_level = cls.rl_pastor
        cls.pastor.save()
        UserDivisionTeam.objects.create(
            user=cls.pastor, division=cls.div_youth, is_primary=True
        )
        pastor_profile = ensure_user_profile(cls.pastor)
        pastor_profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        pastor_profile.save()

        cls.admin = User.objects.create_user(username="staff_admin", password="x")
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.admin,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )


class StaffApplicationServiceTests(StaffApplicationFixture):
    def test_event_staff_status_open_for_approved_applicant(self):
        self.assertEqual(event_staff_status(self.applicant, self.event), "open")

    def test_create_staff_application_for_officer(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )
        self.assertEqual(event_staff_status(self.applicant, self.event), "pending")
        apply_staff_application(application, reviewer=self.admin)
        membership = RetreatGroupMembership.objects.get(
            user=self.applicant, group=self.group
        )
        self.assertEqual(membership.role, RetreatGroupMembership.Role.LEADER)
        attendee = RetreatAttendee.objects.get(
            user=self.applicant, group=self.group
        )
        self.assertEqual(attendee.member_role, RetreatGroupMembership.Role.LEADER)
        self.assertEqual(event_staff_status(self.applicant, self.event), "assigned")

    def test_pastoral_application_approval_creates_council_membership(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.pastor,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.COUNCIL,
            status=RetreatStaffApplication.Status.PENDING,
        )
        apply_staff_application(application, reviewer=self.admin)
        membership = RetreatCouncilMembership.objects.get(
            event=self.event, user=self.pastor
        )
        self.assertEqual(
            membership.role, RetreatCouncilMembership.Role.DIVISION_OBSERVER
        )
        self.assertEqual(membership.division_id, self.div_youth.id)
        application.refresh_from_db()
        self.assertEqual(application.status, RetreatStaffApplication.Status.APPROVED)
        self.assertEqual(
            application.approved_council_role,
            RetreatCouncilMembership.Role.DIVISION_OBSERVER,
        )
        self.assertEqual(event_staff_status(self.pastor, self.event), "assigned")

    def test_vice_leader_approval_creates_membership_and_attendee(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.VICE_LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )
        apply_staff_application(application, reviewer=self.admin)
        membership = RetreatGroupMembership.objects.get(
            user=self.applicant, group=self.group
        )
        self.assertEqual(membership.role, RetreatGroupMembership.Role.VICE_LEADER)
        attendee = RetreatAttendee.objects.get(
            user=self.applicant, group=self.group
        )
        self.assertEqual(
            attendee.member_role, RetreatGroupMembership.Role.VICE_LEADER
        )

    def test_member_council_track_approval_creates_council_membership(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.COUNCIL,
            status=RetreatStaffApplication.Status.PENDING,
        )
        apply_staff_application(application, reviewer=self.admin)
        membership = RetreatCouncilMembership.objects.get(
            event=self.event, user=self.applicant
        )
        self.assertEqual(
            membership.role, RetreatCouncilMembership.Role.DIVISION_OBSERVER
        )
        self.assertEqual(membership.division_id, self.div_youth.id)
        self.assertFalse(
            RetreatGroupMembership.objects.filter(user=self.applicant).exists()
        )

    def test_reject_allows_reapply_when_open(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.VICE_LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )
        reject_staff_application(application, reviewer=self.admin, reason="조 정원 초과")
        self.assertEqual(event_staff_status(self.applicant, self.event), "open")

    def test_duplicate_pending_prevented(self):
        RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )
        with self.assertRaises(Exception):
            RetreatStaffApplication.objects.create(
                event=self.event,
                user=self.applicant,
                region=self.seoul,
                division=self.div_youth,
                application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
                group=self.group,
                group_role=RetreatGroupMembership.Role.VICE_LEADER,
                status=RetreatStaffApplication.Status.PENDING,
            )


class StaffApplicationPageTests(StaffApplicationFixture):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_retreat_home_redirects_approved_applicant_to_staff_apply(self):
        self.client.force_login(self.applicant)
        r = self.client.get(reverse("retreat_home"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            r["Location"],
            reverse("retreat_staff_apply", args=[self.event.id]),
        )

    def test_staff_apply_accessible_for_approved_applicant(self):
        self.client.force_login(self.applicant)
        r = self.client.get(reverse("retreat_staff_apply", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)

    def test_staff_apply_closed_shows_notice_without_redirect(self):
        self.event.staff_applications_open = False
        self.event.save(update_fields=["staff_applications_open"])
        self.client.force_login(self.applicant)
        r = self.client.get(reverse("retreat_staff_apply", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "모집 마감")
        self.assertContains(r, 'id="retreatEventPicker"')

    def test_staff_apply_submit(self):
        self.client.force_login(self.applicant)
        r = self.client.post(
            reverse("retreat_staff_apply", args=[self.event.id]),
            {
                "application_track": StaffApplicationTrack.GROUP_LEADERSHIP,
                "region": str(self.seoul.id),
                "division": str(self.div_youth.id),
                "group": str(self.group.id),
                "group_role": RetreatGroupMembership.Role.LEADER,
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            RetreatStaffApplication.objects.filter(
                user=self.applicant, event=self.event
            ).count(),
            1,
        )

    def test_staff_apply_submit_uses_default_group_leadership_track(self):
        self.client.force_login(self.applicant)
        r = self.client.post(
            reverse("retreat_staff_apply", args=[self.event.id]),
            {
                "region": str(self.seoul.id),
                "division": str(self.div_youth.id),
                "group": str(self.group.id),
                "group_role": RetreatGroupMembership.Role.LEADER,
            },
        )
        self.assertEqual(r.status_code, 302)
        application = RetreatStaffApplication.objects.get(
            user=self.applicant, event=self.event
        )
        self.assertEqual(
            application.application_track, StaffApplicationTrack.GROUP_LEADERSHIP
        )

    def test_staff_apply_pastoral_submit_without_group(self):
        self.client.force_login(self.pastor)
        r = self.client.post(
            reverse("retreat_staff_apply", args=[self.event.id]),
            {
                "region": str(self.seoul.id),
                "division": str(self.div_youth.id),
            },
        )
        self.assertEqual(r.status_code, 302)
        application = RetreatStaffApplication.objects.get(
            user=self.pastor, event=self.event
        )
        self.assertEqual(application.application_track, StaffApplicationTrack.COUNCIL)
        self.assertIsNone(application.group_id)
        self.assertEqual(application.group_role, "")

    def test_staff_apply_rejects_group_from_other_division(self):
        other_div = Division.objects.create(
            region=self.seoul, code="sa_seoul_kids", name="어린이부"
        )
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=other_div,
            name="어린이 1조",
            order=1,
        )
        self.client.force_login(self.applicant)
        r = self.client.post(
            reverse("retreat_staff_apply", args=[self.event.id]),
            {
                "application_track": StaffApplicationTrack.GROUP_LEADERSHIP,
                "region": str(self.seoul.id),
                "division": str(self.div_youth.id),
                "group": str(other_group.id),
                "group_role": RetreatGroupMembership.Role.LEADER,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(
            RetreatStaffApplication.objects.filter(
                user=self.applicant, event=self.event
            ).exists()
        )

    def test_staff_apply_council_track_submit(self):
        self.client.force_login(self.applicant)
        r = self.client.post(
            reverse("retreat_staff_apply", args=[self.event.id]),
            {
                "application_track": StaffApplicationTrack.COUNCIL,
                "region": str(self.seoul.id),
                "division": str(self.div_youth.id),
            },
        )
        self.assertEqual(r.status_code, 302)
        application = RetreatStaffApplication.objects.get(
            user=self.applicant, event=self.event
        )
        self.assertEqual(application.application_track, StaffApplicationTrack.COUNCIL)
        self.assertIsNone(application.group_id)

    def test_staff_apply_council_track_hides_group_fields_on_get(self):
        RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.COUNCIL,
            status=RetreatStaffApplication.Status.PENDING,
        )
        self.client.force_login(self.applicant)
        r = self.client.get(reverse("retreat_staff_apply", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="staffApplyMemberFields" hidden')

    def test_staff_apply_member_without_groups_shows_message(self):
        self.group.delete()
        self.client.force_login(self.applicant)
        r = self.client.get(reverse("retreat_staff_apply", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        affiliation = f"{self.seoul.name} {self.div_youth.name}"
        self.assertContains(r, "귀하의 소속 부서")
        self.assertContains(r, affiliation)
        self.assertContains(r, self.event.name)
        self.assertContains(r, "집회 운영진에게 문의해 주세요")
        self.assertContains(r, "신청 불가")
        self.assertNotContains(r, 'id="staffApplyForm"')
        self.assertNotContains(r, "참가 신청하기")

    def test_staff_apply_page_shows_fixed_affiliation(self):
        self.client.force_login(self.applicant)
        r = self.client.get(reverse("retreat_staff_apply", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "참가 신청서")
        self.assertContains(r, self.div_youth.name)
        self.assertContains(r, "성도")
        self.assertNotContains(r, "신청자 정보")
        self.assertContains(r, "jcc-retreat-staffApplyCardTitle")
        self.assertContains(r, "jcc-pageHeader")
        self.assertContains(r, 'id="retreatEventPicker"')
        self.assertContains(
            r,
            f'value="{StaffApplicationTrack.GROUP_LEADERSHIP}" selected',
        )
        self.assertContains(r, "조 운영진")

    def test_staff_apply_approved_hides_submit_and_shows_notice(self):
        RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.LEADER,
            status=RetreatStaffApplication.Status.APPROVED,
        )
        self.client.force_login(self.applicant)
        r = self.client.get(reverse("retreat_staff_apply", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "참가 신청이 승인되었습니다")
        self.assertContains(r, "다시 신청할 수 있습니다")
        self.assertNotContains(r, "역할 배정 대기")
        self.assertNotContains(r, "참가 신청하기")

    def test_dashboard_forbidden_without_assignment(self):
        self.client.force_login(self.applicant)
        r = self.client.get(reverse("retreat_dashboard", args=[self.event.id]))
        self.assertEqual(r.status_code, 403)


class StaffApplicationScopeTests(StaffApplicationFixture):
    """조 담당 범위(대표+보조) 기준 신청 자격."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.host_div = Division.objects.create(
            region=cls.seoul, code="sa_host_div", name="주관부서"
        )
        cls.host_group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.host_div,
            name="주관 1조",
            order=2,
        )
        cls.extra_scope_user = User.objects.create_user(
            username="staff_extra_scope", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.extra_scope_user, division=cls.div_youth, is_primary=True
        )
        profile = ensure_user_profile(cls.extra_scope_user)
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.save()

        cls.unscoped_div = Division.objects.create(
            region=cls.seoul, code="sa_unscoped_div", name="미배정부서"
        )
        cls.unscoped_user = User.objects.create_user(
            username="staff_unscoped", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.unscoped_user, division=cls.unscoped_div, is_primary=True
        )
        unscoped_profile = ensure_user_profile(cls.unscoped_user)
        unscoped_profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        unscoped_profile.save()

    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_eligible_via_extra_scope_only(self):
        RetreatGroupScope.objects.create(
            group=self.host_group,
            region=self.seoul,
            division=self.div_youth,
        )
        self.group.delete()
        groups = eligible_groups_for_member(self.extra_scope_user, self.event)
        self.assertEqual([g.id for g in groups], [self.host_group.id])
        can_apply, _message = member_can_apply_to_event(
            self.extra_scope_user, self.event, eligible_groups=groups
        )
        self.assertTrue(can_apply)

    def test_extra_scope_user_can_submit_application(self):
        RetreatGroupScope.objects.create(
            group=self.host_group,
            region=self.seoul,
            division=self.div_youth,
        )
        self.group.delete()
        self.client.force_login(self.extra_scope_user)
        r = self.client.post(
            reverse("retreat_staff_apply", args=[self.event.id]),
            {
                "application_track": StaffApplicationTrack.GROUP_LEADERSHIP,
                "region": str(self.seoul.id),
                "division": str(self.div_youth.id),
                "group": str(self.host_group.id),
                "group_role": RetreatGroupMembership.Role.VICE_LEADER,
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            RetreatStaffApplication.objects.filter(
                user=self.extra_scope_user, event=self.event, group=self.host_group
            ).exists()
        )

    def test_unscoped_division_shows_ineligible(self):
        self.client.force_login(self.unscoped_user)
        r = self.client.get(reverse("retreat_staff_apply", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "신청 불가")
        self.assertNotContains(r, 'id="staffApplyForm"')

    def test_representative_scope_still_eligible(self):
        groups = eligible_groups_for_member(self.applicant, self.event)
        self.assertEqual([g.id for g in groups], [self.group.id])


class StaffApplicationApiTests(StaffApplicationFixture):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )

    def test_admin_lists_pending_applications(self):
        self.client.force_login(self.admin)
        r = self.client.get(
            reverse("api_retreat_event_staff_applications", args=[self.event.id])
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["results"]), 1)
        row = r.json()["results"][0]
        self.assertFalse(row["is_council_track"])
        self.assertFalse(row["is_pastoral"])
        self.assertEqual(row["application_track_display"], "조 운영진")

    def test_admin_list_council_track_flags(self):
        RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.pastor,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.COUNCIL,
            status=RetreatStaffApplication.Status.PENDING,
        )
        self.client.force_login(self.admin)
        r = self.client.get(
            reverse("api_retreat_event_staff_applications", args=[self.event.id])
        )
        self.assertEqual(r.status_code, 200)
        results = r.json()["results"]
        self.assertEqual(len(results), 2)
        pastoral_row = next(row for row in results if row["is_pastoral"])
        self.assertTrue(pastoral_row["is_council_track"])
        self.assertEqual(pastoral_row["application_track_display"], "집회 운영진")
        self.assertTrue(pastoral_row["suggested_council_role"])
        group_row = next(row for row in results if not row["is_pastoral"])
        self.assertFalse(group_row["is_council_track"])
        self.assertEqual(group_row["application_track_display"], "조 운영진")

    def test_admin_lists_approved_applications(self):
        apply_staff_application(self.application, reviewer=self.admin)
        self.client.force_login(self.admin)
        r = self.client.get(
            reverse("api_retreat_event_staff_applications", args=[self.event.id]),
            {"status": "approved"},
        )
        self.assertEqual(r.status_code, 200)
        results = r.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], RetreatStaffApplication.Status.APPROVED)

    def test_admin_approves_via_api(self):
        self.client.force_login(self.admin)
        r = self.client.post(
            reverse(
                "api_retreat_staff_application_review",
                args=[self.event.id, self.application.id],
            ),
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, RetreatStaffApplication.Status.APPROVED)
        membership = RetreatGroupMembership.objects.get(
            user=self.applicant, group=self.group
        )
        self.assertEqual(membership.role, RetreatGroupMembership.Role.LEADER)
        self.assertTrue(
            RetreatAttendee.objects.filter(
                user=self.applicant, group=self.group
            ).exists()
        )


class StaffApplicationApprovalOverrideTests(StaffApplicationFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.alt_group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div_youth,
            name="2조",
            order=2,
        )

    def test_approve_with_different_eligible_group(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )
        apply_staff_application(
            application,
            reviewer=self.admin,
            group_id=self.alt_group.id,
            group_role=RetreatGroupMembership.Role.VICE_LEADER,
        )
        application.refresh_from_db()
        self.assertEqual(application.group_id, self.alt_group.id)
        self.assertEqual(application.group_role, RetreatGroupMembership.Role.VICE_LEADER)
        membership = RetreatGroupMembership.objects.get(
            user=self.applicant, group=self.alt_group
        )
        self.assertEqual(membership.role, RetreatGroupMembership.Role.VICE_LEADER)

    def test_approve_rejects_ineligible_group(self):
        other_div = Division.objects.create(
            region=self.seoul, code="sa_other_div", name="어린이부"
        )
        other_group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=other_div,
            name="어린이 1조",
            order=3,
        )
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )
        with self.assertRaises(ValueError):
            apply_staff_application(
                application,
                reviewer=self.admin,
                group_id=other_group.id,
                group_role=RetreatGroupMembership.Role.LEADER,
            )


class StaffApplicationReapplyTests(StaffApplicationFixture):
    def setUp(self):
        super().setUp()
        self.api = APIClient()

    def test_membership_delete_clears_application_and_allows_resubmit(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )
        apply_staff_application(application, reviewer=self.admin)
        membership = RetreatGroupMembership.objects.get(
            user=self.applicant, group=self.group
        )
        self.api.force_authenticate(self.admin)
        r = self.api.delete(
            reverse("api_retreat_group_membership_detail", args=[membership.id])
        )
        self.assertEqual(r.status_code, 204)
        self.assertFalse(
            RetreatStaffApplication.objects.filter(
                event=self.event,
                user=self.applicant,
                status=RetreatStaffApplication.Status.APPROVED,
            ).exists()
        )
        self.assertEqual(event_staff_status(self.applicant, self.event), "open")

        client = Client()
        client.force_login(self.applicant)
        r2 = client.post(
            reverse("retreat_staff_apply", args=[self.event.id]),
            {
                "application_track": StaffApplicationTrack.GROUP_LEADERSHIP,
                "region": str(self.seoul.id),
                "division": str(self.div_youth.id),
                "group": str(self.group.id),
                "group_role": RetreatGroupMembership.Role.VICE_LEADER,
            },
        )
        self.assertEqual(r2.status_code, 302)

    def test_group_delete_keeps_application_when_council_remains(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.seoul,
            division=self.div_youth,
            application_track=StaffApplicationTrack.GROUP_LEADERSHIP,
            group=self.group,
            group_role=RetreatGroupMembership.Role.LEADER,
            status=RetreatStaffApplication.Status.PENDING,
        )
        apply_staff_application(application, reviewer=self.admin)
        RetreatCouncilMembership.objects.create(
            event=self.event,
            user=self.applicant,
            role=RetreatCouncilMembership.Role.EVENT_OBSERVER,
        )
        membership = RetreatGroupMembership.objects.get(
            user=self.applicant, group=self.group
        )
        self.api.force_authenticate(self.admin)
        r = self.api.delete(
            reverse("api_retreat_group_membership_detail", args=[membership.id])
        )
        self.assertEqual(r.status_code, 204)
        self.assertTrue(
            RetreatStaffApplication.objects.filter(
                event=self.event,
                user=self.applicant,
                status=RetreatStaffApplication.Status.APPROVED,
            ).exists()
        )
        self.assertFalse(
            delete_staff_application_if_unassigned(
                self.applicant, self.event, actor=self.admin
            )
        )
