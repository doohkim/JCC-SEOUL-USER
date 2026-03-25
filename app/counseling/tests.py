"""상담 API·권한 테스트."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from counseling.models import CounselingRequest, CounselingSlot
from counseling.services import ensure_slots_for_horizon, get_or_create_schedule_settings
from users.models import Division, RoleLevel, UserDivisionTeam

User = get_user_model()


class CounselingApiTests(TestCase):
    def setUp(self):
        self.div_a = Division.objects.create(name="부서A", code="div-a", sort_order=1)
        self.div_b = Division.objects.create(name="부서B", code="div-b", sort_order=2)
        self.rl_pastor = RoleLevel.objects.create(name="목사", code="pastor", level=100, sort_order=0)
        self.rl_member = RoleLevel.objects.create(name="일반", code="member", level=0, sort_order=10)

        self.counselor = User.objects.create_user(username="pastor_a", password="x")
        self.counselor.role_level = self.rl_pastor
        self.counselor.save()
        UserDivisionTeam.objects.create(user=self.counselor, division=self.div_a, is_primary=True)

        self.counselor_b = User.objects.create_user(username="pastor_b", password="x")
        self.counselor_b.role_level = self.rl_pastor
        self.counselor_b.save()
        UserDivisionTeam.objects.create(user=self.counselor_b, division=self.div_b, is_primary=True)

        self.applicant = User.objects.create_user(username="member_a", password="x")
        self.applicant.role_level = self.rl_member
        self.applicant.save()
        UserDivisionTeam.objects.create(user=self.applicant, division=self.div_a, is_primary=True)

        self.stranger = User.objects.create_user(username="stranger", password="x")
        self.stranger.role_level = self.rl_member
        self.stranger.save()
        UserDivisionTeam.objects.create(user=self.stranger, division=self.div_b, is_primary=True)

        get_or_create_schedule_settings(self.counselor.pk)
        ensure_slots_for_horizon(self.counselor.pk)
        self.slot = (
            CounselingSlot.objects.filter(
                counselor_id=self.counselor.pk,
                state=CounselingSlot.State.OPEN,
            )
            .order_by("date", "start_time")
            .first()
        )
        self.assertIsNotNone(self.slot)

    def test_counselor_list_division_scoped(self):
        c = APIClient()
        c.force_login(self.applicant)
        r = c.get("/api/v1/counseling/counselors/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in r.json()]
        self.assertIn(self.counselor.pk, ids)
        self.assertNotIn(self.counselor_b.pk, ids)

    def test_create_request_and_block_double_book(self):
        c = APIClient()
        c.force_login(self.applicant)
        r = c.post(
            "/api/v1/counseling/requests/",
            {"slot_id": self.slot.pk, "applicant_message": "hello"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        r2 = c.post(
            "/api/v1/counseling/requests/",
            {"slot_id": self.slot.pk, "applicant_message": "again"},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stranger_cannot_read_request(self):
        c1 = APIClient()
        c1.force_login(self.applicant)
        res = c1.post(
            "/api/v1/counseling/requests/",
            {"slot_id": self.slot.pk, "applicant_message": "x"},
            format="json",
        )
        public_id = res.json()["public_id"]

        c2 = APIClient()
        c2.force_login(self.stranger)
        r = c2.get(f"/api/v1/counseling/requests/{public_id}/")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_counselor_settings_forbidden_for_member(self):
        c = APIClient()
        c.force_login(self.applicant)
        r = c.get("/api/v1/counseling/counselor/settings/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
