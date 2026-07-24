"""집회당 user → 조원 1행 + 역할별 소속·겸직 테스트."""

from __future__ import annotations

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from retreat.models import (
    Lodging,
    LodgingRoom,
    RetreatAttendee,
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatPickup,
)
from retreat.services.onboarding import apply_retreat_membership_on_approval
from users.models import Division, Region, UserProfile

User = get_user_model()


class _AttendeeDedupFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="dedup_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="중복 정리 집회",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        cls.group1 = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="1조",
        )
        cls.group2 = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.div,
            name="2조",
        )
        cls.council = User.objects.create_user(username="dedup_council", password="x")
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )
        cls.leader2 = User.objects.create_user(username="dedup_leader2", password="x")
        RetreatGroupMembership.objects.create(
            user=cls.leader2,
            group=cls.group2,
            role=RetreatGroupMembership.Role.LEADER,
        )


class AttendeeDedupOnboardingTests(_AttendeeDedupFixture):
    def test_onboarding_member_then_other_group_leader_moves_home(self):
        """1조 조원 온보딩 후 2조 조장 지정 시 소속을 2조로 이동."""
        applicant = User.objects.create_user(username="dedup_kim", password="x")
        profile = UserProfile.objects.create(
            user=applicant,
            real_name="김필중",
            requested_retreat_participation=True,
            requested_retreat_event=self.event,
            requested_retreat_group=self.group1,
            requested_retreat_role="participant",
        )
        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group1.id),
            retreat_role="participant",
            changed_by=self.council,
            appoint_leadership=False,
        )
        self.assertTrue(
            RetreatAttendee.objects.filter(group=self.group1, user=applicant).exists()
        )

        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group2.id),
            retreat_role="leader",
            changed_by=self.council,
            appoint_leadership=True,
        )

        self.assertFalse(
            RetreatAttendee.objects.filter(group=self.group1, user=applicant).exists()
        )
        home = RetreatAttendee.objects.get(group=self.group2, user=applicant)
        self.assertEqual(home.member_role, RetreatAttendee.MemberRole.LEADER)
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=self.group2, user=applicant, role="leader"
            ).exists()
        )
        self.assertEqual(
            RetreatAttendee.objects.filter(
                user=applicant, group__event=self.event
            ).count(),
            1,
        )

    def test_onboarding_sets_lodging_stay_status(self):
        applicant = User.objects.create_user(username="dedup_stay", password="x")
        profile = UserProfile.objects.create(
            user=applicant,
            requested_retreat_participation=True,
            requested_retreat_event=self.event,
            requested_retreat_group=self.group1,
        )
        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group1.id),
            retreat_role="participant",
            changed_by=self.council,
            appoint_leadership=False,
        )
        attendee = RetreatAttendee.objects.get(group=self.group1, user=applicant)
        self.assertIsNotNone(attendee.lodging_stay_status)
        self.assertEqual(
            attendee.lodging_stay_status,
            RetreatAttendee.LodgingStayStatus.NO_STAY,
        )

    def test_consolidate_does_not_mirror_profile_requested_retreat_group(self):
        applicant = User.objects.create_user(username="dedup_profile", password="x")
        profile = UserProfile.objects.create(
            user=applicant,
            requested_retreat_participation=True,
            requested_retreat_event=self.event,
            requested_retreat_group=self.group1,
        )
        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group1.id),
            retreat_role="participant",
            changed_by=self.council,
            appoint_leadership=False,
        )
        apply_retreat_membership_on_approval(
            user=applicant,
            profile=profile,
            retreat_group_id=str(self.group2.id),
            retreat_role="leader",
            changed_by=self.council,
            appoint_leadership=True,
        )
        profile.refresh_from_db()
        self.assertEqual(profile.requested_retreat_group_id, self.group1.id)
        self.assertTrue(
            RetreatAttendee.objects.filter(group=self.group2, user=applicant).exists()
        )
        self.assertTrue(
            RetreatGroupMembership.objects.filter(
                group=self.group2, user=applicant, role="leader"
            ).exists()
        )


class AttendeeDedupMembershipApiTests(_AttendeeDedupFixture):
    def setUp(self):
        self.client = APIClient()

    def test_membership_api_member_moves_home_to_new_group(self):
        target = User.objects.create_user(username="dedup_api", password="x")
        UserProfile.objects.create(
            user=target,
            real_name="이동조원",
            requested_retreat_participation=True,
            requested_retreat_event=self.event,
            requested_retreat_group=self.group1,
        )
        apply_retreat_membership_on_approval(
            user=target,
            profile=target.profile,
            retreat_group_id=str(self.group1.id),
            retreat_role="participant",
            changed_by=self.council,
            appoint_leadership=False,
        )
        room_lodging = Lodging.objects.create(event=self.event, name="본관")
        room = LodgingRoom.objects.create(
            lodging=room_lodging,
            number="A-1",
            capacity=4,
            recommended_gender=LodgingRoom.Gender.MALE,
            region=self.seoul,
            division=self.div,
        )
        home = RetreatAttendee.objects.get(group=self.group1, user=target)
        home.check_in_status = RetreatAttendee.CheckInStatus.CHECKED_IN
        home.lodging_room = room
        home.gender = RetreatAttendee.Gender.MALE
        home.save()
        RetreatPickup.objects.create(
            event=self.event,
            group=self.group1,
            name=home.name,
            direction=RetreatPickup.Direction.ARRIVAL,
            number=1,
            train_time=timezone.make_aware(datetime(2026, 8, 1, 10, 0)),
            boarding_place="장성역",
            contact="010-1111-2222",
        )

        self.client.force_authenticate(self.leader2)
        url = reverse("api_retreat_group_memberships", args=[self.group2.id])
        r = self.client.post(
            url, {"user_id": target.id, "role": "leader"}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.content)
        data = r.json()
        self.assertTrue(data.get("moved_home_group"))
        self.assertFalse(data.get("kept_home_group"))
        self.assertEqual(data.get("home_group_id"), self.group2.id)
        self.assertFalse(
            RetreatAttendee.objects.filter(group=self.group1, user=target).exists()
        )
        moved = RetreatAttendee.objects.get(group=self.group2, user=target)
        self.assertEqual(moved.member_role, RetreatAttendee.MemberRole.LEADER)
        self.assertEqual(
            moved.check_in_status, RetreatAttendee.CheckInStatus.CHECKED_IN
        )
        self.assertIsNone(moved.lodging_room_id)
        self.assertTrue(
            RetreatPickup.objects.filter(
                event=self.event, group=self.group2, name=moved.name
            ).exists()
        )
        self.assertFalse(
            RetreatPickup.objects.filter(
                event=self.event, group=self.group1, name=moved.name
            ).exists()
        )

    def test_membership_api_leader_keeps_home_adds_cross_group(self):
        target = User.objects.create_user(username="dedup_leader_keep", password="x")
        UserProfile.objects.create(user=target, real_name="겸직조장")
        self.client.force_authenticate(self.council)
        r1 = self.client.post(
            reverse("api_retreat_group_memberships", args=[self.group1.id]),
            {"user_id": target.id, "role": "leader"},
            format="json",
        )
        self.assertEqual(r1.status_code, 201, r1.content)
        self.client.force_authenticate(self.leader2)
        r2 = self.client.post(
            reverse("api_retreat_group_memberships", args=[self.group2.id]),
            {"user_id": target.id, "role": "leader"},
            format="json",
        )
        self.assertEqual(r2.status_code, 201, r2.content)
        data = r2.json()
        self.assertTrue(data.get("kept_home_group"))
        self.assertTrue(data.get("is_cross_group_leader"))
        self.assertEqual(data.get("home_group_id"), self.group1.id)
        self.assertTrue(
            RetreatAttendee.objects.filter(group=self.group1, user=target).exists()
        )
        self.assertFalse(
            RetreatAttendee.objects.filter(group=self.group2, user=target).exists()
        )
        self.assertEqual(
            RetreatAttendee.objects.filter(
                user=target, group__event=self.event
            ).count(),
            1,
        )


class SameGroupUserLinkUniquenessTests(_AttendeeDedupFixture):
    """집회당 계정↔조원 1:1 — 같은 조 중복 연동도 거부."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.council)

    def test_cannot_create_second_attendee_with_same_user_in_same_group(self):
        target = User.objects.create_user(username="dedup_same_group", password="x")
        UserProfile.objects.create(user=target, real_name="동일계정")
        url = reverse("api_retreat_group_attendees", args=[self.group1.id])
        r1 = self.client.post(
            url,
            {"user": target.id, "name": "동일계정", "member_role": "vice_leader"},
            format="json",
        )
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self.client.post(
            url,
            {"user": target.id, "name": "동일계정", "member_role": "vice_leader"},
            format="json",
        )
        self.assertEqual(r2.status_code, 400, r2.content)
        self.assertIn("user", r2.json())
        self.assertEqual(
            RetreatAttendee.objects.filter(
                user=target, group__event=self.event
            ).count(),
            1,
        )

    def test_cannot_patch_other_attendee_to_already_linked_user(self):
        target = User.objects.create_user(username="dedup_patch_link", password="x")
        UserProfile.objects.create(user=target, real_name="패치연동")
        linked = RetreatAttendee.objects.create(
            group=self.group1,
            user=target,
            name="패치연동",
            member_role=RetreatAttendee.MemberRole.VICE_LEADER,
        )
        other = RetreatAttendee.objects.create(
            group=self.group1,
            name="미연동행",
            member_role=RetreatAttendee.MemberRole.VICE_LEADER,
        )
        r = self.client.patch(
            reverse("api_retreat_attendee_detail", args=[other.id]),
            {"user": target.id},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("user", r.json())
        other.refresh_from_db()
        self.assertIsNone(other.user_id)
        linked.refresh_from_db()
        self.assertEqual(linked.user_id, target.id)

    def test_can_keep_same_user_on_patch(self):
        target = User.objects.create_user(username="dedup_keep_link", password="x")
        UserProfile.objects.create(user=target, real_name="유지연동")
        attendee = RetreatAttendee.objects.create(
            group=self.group1,
            user=target,
            name="유지연동",
            member_role=RetreatAttendee.MemberRole.MEMBER,
        )
        r = self.client.patch(
            reverse("api_retreat_attendee_detail", args=[attendee.id]),
            {"user": target.id, "memo": "ok"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        attendee.refresh_from_db()
        self.assertEqual(attendee.user_id, target.id)
        self.assertEqual(attendee.memo, "ok")
