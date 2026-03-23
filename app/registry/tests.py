"""교적·조직 동기화."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from registry.models import Member, MemberDivisionTeam
from users.models import Division, Team, UserDivisionTeam

User = get_user_model()


class LinkedUserOrgSyncTests(TestCase):
    def setUp(self):
        self.div_youth = Division.objects.create(name="청년부", code="youth", sort_order=1)
        self.team_a = Team.objects.create(
            division=self.div_youth, name="A팀", code="a", sort_order=1
        )
        self.team_b = Team.objects.create(
            division=self.div_youth, name="B팀", code="b", sort_order=2
        )
        self.user = User.objects.create_user(username="syncuser", password="x")
        self.member = Member.objects.create(name="동기화테스트", linked_user=self.user)

    def test_mdt_create_updates_user_division_team(self):
        MemberDivisionTeam.objects.create(
            member=self.member,
            division=self.div_youth,
            team=self.team_a,
            is_primary=True,
            sort_order=0,
        )
        udt = UserDivisionTeam.objects.get(
            user=self.user, division=self.div_youth, team=self.team_a
        )
        self.assertTrue(udt.is_primary)

    def test_mdt_team_change_updates_user_row(self):
        mdt = MemberDivisionTeam.objects.create(
            member=self.member,
            division=self.div_youth,
            team=self.team_a,
            is_primary=True,
            sort_order=0,
        )
        mdt.team = self.team_b
        mdt.save(update_fields=["team"])
        self.assertFalse(
            UserDivisionTeam.objects.filter(
                user=self.user, division=self.div_youth, team=self.team_a
            ).exists()
        )
        self.assertTrue(
            UserDivisionTeam.objects.filter(
                user=self.user, division=self.div_youth, team=self.team_b
            ).exists()
        )

    def test_mdt_delete_one_team_removes_only_that_user_row(self):
        ma = MemberDivisionTeam.objects.create(
            member=self.member,
            division=self.div_youth,
            team=self.team_a,
            is_primary=True,
            sort_order=0,
        )
        MemberDivisionTeam.objects.create(
            member=self.member,
            division=self.div_youth,
            team=self.team_b,
            is_primary=False,
            sort_order=1,
        )
        ma.delete()
        self.assertFalse(
            UserDivisionTeam.objects.filter(
                user=self.user, division=self.div_youth, team=self.team_a
            ).exists()
        )
        self.assertTrue(
            UserDivisionTeam.objects.filter(
                user=self.user, division=self.div_youth, team=self.team_b
            ).exists()
        )
