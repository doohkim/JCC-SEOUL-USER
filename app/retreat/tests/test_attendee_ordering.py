"""조원 정렬·조 카드 조장 표시 우선순위 테스트."""

from __future__ import annotations

from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from users.models import Division, Region, User
from retreat.models import (
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
from retreat.services.attendee_ordering import (
    order_attendees_for_member_list,
    pick_group_card_leader_name,
    pick_group_card_leader_name_from_memberships,
    resolve_group_card_leader_name,
)
from users.mixins import ensure_user_profile


class PickGroupCardLeaderNameTests(TestCase):
    def setUp(self):
        self.seoul = Region.objects.get(code="seoul")
        self.division = Division.objects.create(
            region=self.seoul, code="order_college", name="대학부"
        )
        self.event = RetreatEvent.objects.create(
            name="집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        self.group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.division,
            name="1조",
            order=1,
        )
        self.linked_user = User.objects.create_user(
            username="linked_leader", password="x"
        )

    def _leader(self, **kwargs):
        defaults = {
            "group": self.group,
            "member_role": RetreatAttendee.MemberRole.LEADER,
            "check_in_status": RetreatAttendee.CheckInStatus.PENDING,
        }
        defaults.update(kwargs)
        return RetreatAttendee.objects.create(**defaults)

    def test_prefers_checked_in_over_pending(self):
        self._leader(
            name="입실전조장", check_in_status=RetreatAttendee.CheckInStatus.PENDING
        )
        checked_in = self._leader(
            name="입실조장",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
        )
        leaders = list(
            RetreatAttendee.objects.filter(
                group=self.group, member_role=RetreatAttendee.MemberRole.LEADER
            )
        )
        self.assertEqual(pick_group_card_leader_name(leaders), checked_in.name)

    def test_excludes_checked_out(self):
        self._leader(
            name="퇴실조장",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        pending = self._leader(
            name="입실전조장",
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        leaders = list(
            RetreatAttendee.objects.filter(
                group=self.group, member_role=RetreatAttendee.MemberRole.LEADER
            )
        )
        self.assertEqual(pick_group_card_leader_name(leaders), pending.name)

    def test_prefers_linked_user_when_check_in_equal(self):
        self._leader(name="미연동조장")
        linked = self._leader(name="연동조장", user=self.linked_user)
        leaders = list(
            RetreatAttendee.objects.filter(
                group=self.group, member_role=RetreatAttendee.MemberRole.LEADER
            )
        )
        self.assertEqual(pick_group_card_leader_name(leaders), linked.name)

    def test_falls_back_to_first_registered(self):
        first = self._leader(name="김첫조장")
        self._leader(name="김둘조장")
        leaders = list(
            RetreatAttendee.objects.filter(
                group=self.group, member_role=RetreatAttendee.MemberRole.LEADER
            )
        )
        self.assertEqual(pick_group_card_leader_name(leaders), first.name)

    def test_membership_fallback_for_cross_group_leader(self):
        """담당조(명단 없음)는 membership 조장 이름을 쓴다."""
        user = User.objects.create_user(username="cross_leader", password="x")
        profile = ensure_user_profile(user)
        profile.real_name = "겸직조장"
        profile.save(update_fields=["real_name", "updated_at"])
        membership = RetreatGroupMembership.objects.create(
            user=user,
            group=self.group,
            role=RetreatGroupMembership.Role.LEADER,
        )
        self.assertEqual(
            pick_group_card_leader_name_from_memberships([membership]),
            "겸직조장",
        )
        self.assertEqual(
            resolve_group_card_leader_name([], [membership]),
            "겸직조장",
        )

    def test_attendee_leader_preferred_over_membership(self):
        user = User.objects.create_user(username="mem_only", password="x")
        profile = ensure_user_profile(user)
        profile.real_name = "멤버십조장"
        profile.save(update_fields=["real_name", "updated_at"])
        membership = RetreatGroupMembership.objects.create(
            user=user,
            group=self.group,
            role=RetreatGroupMembership.Role.LEADER,
        )
        attendee = self._leader(name="명단조장")
        self.assertEqual(
            resolve_group_card_leader_name([attendee], [membership]),
            "명단조장",
        )


class AttendeeMemberListOrderTests(TestCase):
    def setUp(self):
        self.seoul = Region.objects.get(code="seoul")
        self.division = Division.objects.create(
            region=self.seoul, code="order_college", name="대학부"
        )
        self.event = RetreatEvent.objects.create(
            name="집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        self.group = RetreatGroup.objects.create(
            event=self.event,
            region=self.seoul,
            division=self.division,
            name="1조",
            order=1,
        )
        now = timezone.now()

    def _attendee(self, **kwargs):
        defaults = {
            "group": self.group,
            "name": "조원",
            "member_role": RetreatAttendee.MemberRole.MEMBER,
            "check_in_status": RetreatAttendee.CheckInStatus.PENDING,
        }
        defaults.update(kwargs)
        return RetreatAttendee.objects.create(**defaults)

    def test_orders_check_in_before_role(self):
        checked_in_member = self._attendee(
            name="입실조원",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            checked_in_at=timezone.now(),
        )
        pending_leader = self._attendee(
            name="입실전조장",
            member_role=RetreatAttendee.MemberRole.LEADER,
        )
        checked_out_leader = self._attendee(
            name="퇴실조장",
            member_role=RetreatAttendee.MemberRole.LEADER,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        ordered = list(
            order_attendees_for_member_list(
                RetreatAttendee.objects.filter(group=self.group)
            )
        )
        self.assertEqual(
            [a.id for a in ordered],
            [checked_in_member.id, pending_leader.id, checked_out_leader.id],
        )

    def test_orders_role_within_same_check_in_status(self):
        leader = self._attendee(
            name="조장",
            member_role=RetreatAttendee.MemberRole.LEADER,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            checked_in_at=timezone.now(),
        )
        vice = self._attendee(
            name="부조장",
            member_role=RetreatAttendee.MemberRole.VICE_LEADER,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            checked_in_at=timezone.now() + timedelta(minutes=5),
        )
        teacher = self._attendee(
            name="선생님",
            member_role=RetreatAttendee.MemberRole.TEACHER,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            checked_in_at=timezone.now() + timedelta(minutes=7),
        )
        member = self._attendee(
            name="조원",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            checked_in_at=timezone.now() + timedelta(minutes=10),
        )
        ordered = list(
            order_attendees_for_member_list(
                RetreatAttendee.objects.filter(group=self.group)
            )
        )
        self.assertEqual(
            [a.id for a in ordered], [leader.id, vice.id, teacher.id, member.id]
        )

    def test_orders_checked_in_at_within_same_status_and_role(self):
        earlier = self._attendee(
            name="먼저입실",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            checked_in_at=timezone.now(),
        )
        later = self._attendee(
            name="나중입실",
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            checked_in_at=timezone.now() + timedelta(hours=1),
        )
        ordered = list(
            order_attendees_for_member_list(
                RetreatAttendee.objects.filter(group=self.group)
            )
        )
        self.assertEqual([a.id for a in ordered], [earlier.id, later.id])


class ManageGroupsCardLeaderDisplayTests(TestCase):
    """조 관리 목록 카드에 조장 이름 우선순위가 반영되는지."""

    @classmethod
    def setUpTestData(cls):
        from retreat.models import RetreatCouncilMembership
        from users.models import RoleLevel

        cls.seoul = Region.objects.get(code="seoul")
        cls.division = Division.objects.create(
            region=cls.seoul, code="card_youth", name="청년부"
        )
        cls.event = RetreatEvent.objects.create(
            name="집회",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        cls.group = RetreatGroup.objects.create(
            event=cls.event,
            region=cls.seoul,
            division=cls.division,
            name="1조",
            order=1,
        )
        cls.council_user = User.objects.create_user(
            username="council_card", password="x"
        )
        president, _ = RoleLevel.objects.get_or_create(
            code="president",
            defaults={"name": "회장", "level": 80, "sort_order": 20},
        )
        cls.council_user.role_level = president
        cls.council_user.save(update_fields=["role_level"])
        RetreatCouncilMembership.objects.create(
            event=cls.event,
            user=cls.council_user,
            role=RetreatCouncilMembership.Role.EVENT_ADMIN,
        )

    def test_manage_groups_card_shows_priority_leader_name(self):
        from django.test import Client

        RetreatAttendee.objects.create(
            group=self.group,
            name="김첫조장",
            member_role=RetreatAttendee.MemberRole.LEADER,
            sort_order=0,
        )
        RetreatAttendee.objects.create(
            group=self.group,
            name="김입실조장",
            member_role=RetreatAttendee.MemberRole.LEADER,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            checked_in_at=timezone.now(),
            sort_order=1,
        )
        client = Client()
        client.force_login(self.council_user)
        r = client.get(reverse("retreat_group_manage_list", args=[self.event.id]))
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn("조장 김입실조장", content)
        self.assertNotIn("김첫조장", content)
