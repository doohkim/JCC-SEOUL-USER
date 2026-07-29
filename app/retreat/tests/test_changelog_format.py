"""변경 이력 문장 변환 테스트."""

from __future__ import annotations

from datetime import date

from django.test import TestCase, override_settings

from retreat.models import (
    RetreatChangeLog,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatStaffApplication,
    StaffApplicationTrack,
)
from retreat.services.changelog_format import (
    _diff_lines,
    _format_value,
    humanize_change_log,
)
from users.models import Division, Region, User, UserProfile


@override_settings(TIME_ZONE="Asia/Seoul", USE_TZ=True)
class ChangelogFormatDatetimeTests(TestCase):
    def test_format_value_formats_iso_datetime_without_seconds(self):
        self.assertEqual(
            _format_value(
                "checked_in_at",
                "2026-06-12T14:16:54.797865+00:00",
            ),
            "2026.06.12 23:16",
        )
        self.assertEqual(
            _format_value(
                "expected_check_in_at",
                "2026-06-18T14:15:00+00:00",
            ),
            "2026.06.18 23:15",
        )
        self.assertEqual(
            _format_value(
                "expected_check_in_at",
                "2026-06-18T23:15:00+09:00",
            ),
            "2026.06.18 23:15",
        )

    def test_diff_lines_use_human_readable_datetimes(self):
        lines = _diff_lines(
            {
                "check_in_status": "pending",
                "checked_in_at": "2026-06-12T14:16:54.797865+00:00",
            },
            {
                "check_in_status": "checked_in",
                "checked_in_at": "2026-06-18T14:15:29.363881+00:00",
            },
        )
        joined = "; ".join(lines)
        self.assertIn("입·퇴실: 입실전 → 입실", joined)
        self.assertIn("실제 입실 시각: 2026.06.12 23:16 → 2026.06.18 23:15", joined)
        self.assertNotIn("T14:16:54", joined)


class ChangelogHumanReadableStaffTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = RetreatEvent.objects.create(
            name="변경 이력 집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
        )
        cls.actor = User.objects.create_user(username="actor")
        UserProfile.objects.create(user=cls.actor, real_name="김관리")
        cls.target = User.objects.create_user(username="target")
        UserProfile.objects.create(user=cls.target, real_name="이운영")
        cls.membership = RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.target,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

    def test_existing_staff_log_resolves_person_and_role_labels(self):
        log = RetreatChangeLog.objects.create(
            event=self.event,
            changed_by=self.actor,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=self.membership.id,
            payload_after={
                "staff": True,
                "role": "event_admin",
                "note": "",
            },
        )

        entry = humanize_change_log(log)

        self.assertEqual(entry.target_label, "집회 운영진")
        self.assertEqual(entry.action_label, "권한 변경")
        self.assertEqual(
            entry.summary,
            "김관리님이 이운영님의 집회 운영 권한을 집회 전체 관리자로 설정했습니다.",
        )
        self.assertNotIn("event_admin", " ".join(entry.detail))
        self.assertNotIn("staff", " ".join(entry.detail))

    def test_role_change_explains_before_and_after_in_korean(self):
        log = RetreatChangeLog.objects.create(
            event=self.event,
            changed_by=self.actor,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=self.membership.id,
            payload_before={
                "staff": True,
                "user_id": self.target.id,
                "role": "event_observer",
            },
            payload_after={
                "staff": True,
                "user_id": self.target.id,
                "role": "event_admin",
            },
        )

        entry = humanize_change_log(log)

        self.assertIn(
            "이운영님의 집회 운영 권한을 집회 전체 관찰자에서 "
            "집회 전체 관리자 역할로 변경했습니다.",
            entry.summary,
        )
        self.assertEqual(
            entry.detail,
            ["역할: 집회 전체 관찰자 → 집회 전체 관리자"],
        )


class ChangelogStaffApplicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = RetreatEvent.objects.create(
            name="신청 이력 집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
        )
        cls.region, _ = Region.objects.get_or_create(
            code="changelog_region",
            defaults={"name": "서울", "sort_order": 1},
        )
        cls.division = Division.objects.create(
            region=cls.region,
            code="changelog_division",
            name="청년부",
        )
        cls.reviewer = User.objects.create_user(username="reviewer")
        UserProfile.objects.create(user=cls.reviewer, real_name="김승인")
        cls.applicant = User.objects.create_user(username="applicant")
        UserProfile.objects.create(user=cls.applicant, real_name="박신청")

    def test_approval_log_shows_applicant_real_name(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.region,
            division=self.division,
            application_track=StaffApplicationTrack.COUNCIL,
            status=RetreatStaffApplication.Status.APPROVED,
            approved_council_role="event_admin",
        )
        log = RetreatChangeLog.objects.create(
            event=self.event,
            changed_by=self.reviewer,
            action=RetreatChangeLog.Action.APPROVE,
            target_type=RetreatChangeLog.TargetType.STAFF_APPLICATION,
            target_id=application.id,
            payload_before={"status": "pending"},
            payload_after={
                "status": "approved",
                "approved_council_role": "event_admin",
            },
        )

        entry = humanize_change_log(log)

        self.assertEqual(entry.target_label, "운영진 신청")
        self.assertEqual(entry.action_label, "승인")
        self.assertEqual(
            entry.summary,
            "김승인님이 박신청님의 집회 운영진 신청을 승인했습니다. "
            "(집회 전체 관리자)",
        )
        self.assertNotIn("staff_application", entry.summary)
        self.assertNotIn("event_admin", " ".join(entry.detail))

    def test_deleted_application_uses_user_id_from_log(self):
        application = RetreatStaffApplication.objects.create(
            event=self.event,
            user=self.applicant,
            region=self.region,
            division=self.division,
            application_track=StaffApplicationTrack.COUNCIL,
        )
        application_id = application.id
        application.delete()
        log = RetreatChangeLog.objects.create(
            event=self.event,
            changed_by=self.reviewer,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.STAFF_APPLICATION,
            target_id=application_id,
            payload_before={
                "user": self.applicant.id,
                "status": "approved",
            },
        )

        entry = humanize_change_log(log)

        self.assertEqual(
            entry.summary,
            "김승인님이 박신청님의 승인된 운영진 신청 기록을 삭제했습니다.",
        )


class ChangelogPickupTests(TestCase):
    def test_deleted_pickup_log_shows_attendee_name_and_korean_details(self):
        event = RetreatEvent.objects.create(
            name="픽업 이력 집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
        )
        actor = User.objects.create_user(username="pickup_actor")
        UserProfile.objects.create(user=actor, real_name="이경업")
        log = RetreatChangeLog.objects.create(
            event=event,
            changed_by=actor,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.PICKUP,
            target_id=41,
            payload_before={
                "applicant_name": "이경업",
                "boarding_place": "장성역",
                "contact": "010-7714-9642",
                "direction": "arrival",
                "name": "김채은",
                "number": 18,
                "train_time": "2026-07-31T13:40:00+00:00",
            },
        )

        entry = humanize_change_log(log)

        self.assertEqual(
            entry.summary,
            "이경업님이 김채은님의 입회 픽업 신청을 삭제했습니다. (장성역)",
        )
        self.assertEqual(
            entry.detail,
            [
                "탑승장소: 장성역",
                "이동 시각: 2026.07.31 22:40",
                "연락처: 010-7714-9642",
            ],
        )
        self.assertNotIn("#41", entry.summary)
        self.assertNotIn("arrival", " ".join(entry.detail))


class ChangelogNoInternalIdsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = RetreatEvent.objects.create(
            name="이름 표시 집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
        )
        cls.region, _ = Region.objects.get_or_create(
            code="changelog_name_region",
            defaults={"name": "서울", "sort_order": 1},
        )
        cls.division = Division.objects.create(
            region=cls.region,
            code="changelog_name_division",
            name="청년부",
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.region,
            division=cls.division,
            name="8조",
        )
        cls.actor = User.objects.create_user(username="name_actor")
        UserProfile.objects.create(user=cls.actor, real_name="김관리")
        cls.target = User.objects.create_user(username="name_target")
        UserProfile.objects.create(user=cls.target, real_name="박조장")

    def test_group_log_uses_group_name_instead_of_id(self):
        log = RetreatChangeLog.objects.create(
            event=self.event,
            changed_by=self.actor,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.GROUP,
            target_id=self.group.id,
            payload_before={"name": "7조"},
            payload_after={"name": "8조"},
        )

        entry = humanize_change_log(log)

        self.assertIn("7조의 이름을 8조", entry.summary)
        self.assertNotIn(f"#{self.group.id}", entry.summary)

    def test_deleted_group_staff_log_resolves_group_user_and_role(self):
        membership = RetreatGroupMembership.objects.create(
            group=self.group,
            user=self.target,
            role=RetreatGroupMembership.Role.LEADER,
        )
        membership_id = membership.id
        membership.delete()
        log = RetreatChangeLog.objects.create(
            event=self.event,
            changed_by=self.actor,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=membership_id,
            payload_before={
                "group_id": self.group.id,
                "user_id": self.target.id,
                "role": "leader",
            },
        )

        entry = humanize_change_log(log)

        self.assertEqual(
            entry.summary,
            "김관리님이 박조장님의 8조 운영 권한을 해제했습니다.",
        )
        self.assertNotIn("leader", " ".join(entry.detail))

    def test_status_and_roles_are_korean_labels(self):
        lines = _diff_lines(
            {
                "check_in_status": "pending",
                "member_role": "member",
                "lodging_stay_status": "unassigned",
            },
            {
                "check_in_status": "checked_in",
                "member_role": "leader",
                "lodging_stay_status": "active",
            },
        )

        self.assertIn("입·퇴실: 입실전 → 입실", lines)
        self.assertIn("조 역할: 조원 → 조장", lines)
        self.assertIn("숙박 상태: 미배정 → 숙박 중", lines)
