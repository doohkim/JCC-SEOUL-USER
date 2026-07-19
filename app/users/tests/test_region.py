"""Region(지역) 도입 회귀 테스트.

3가지 축:
1. 모델: Region 모델 + Division.region NOT NULL FK 동작
2. 마이그레이션 결과: 시드된 기본 Region(seoul/incheon) 및 기존 Division 백필
3. 권한 스코프: region 인자 옵션이 기본 동작을 변경하지 않고, 지정 시 부서를
   해당 지역으로 좁혀줌
"""

from __future__ import annotations

from django.db import IntegrityError
from django.test import TestCase

from users.models import Division, Region, RoleLevel, User, UserDivisionTeam
from users.permissions import (
    dashboard_divisions_for,
    membership_divisions_for,
    pastoral_divisions_for,
    registry_divisions_for,
    visible_divisions_for,
    visible_regions_for,
)


class RegionModelTests(TestCase):
    def test_create_region(self):
        r = Region.objects.create(code="busan", name="부산", sort_order=30)
        self.assertEqual(str(r), "부산")
        self.assertEqual(r.code, "busan")

    def test_region_code_unique(self):
        Region.objects.create(code="busan", name="부산")
        with self.assertRaises(IntegrityError):
            Region.objects.create(code="busan", name="중복")

    def test_division_requires_region(self):
        """Division.region 은 NOT NULL — region 없이 만들면 실패."""
        with self.assertRaises(IntegrityError):
            Division.objects.create(code="no_region_div", name="지역없음")

    def test_division_str_prefixes_region(self):
        region = Region.objects.create(code="busan", name="부산", sort_order=30)
        div = Division.objects.create(region=region, code="busan_youth", name="청년부")
        self.assertEqual(str(div), "부산 · 청년부")


class RegionMigrationTests(TestCase):
    """0009 마이그레이션 결과(시드 + 기존 Division 백필) 검증."""

    def test_seeded_regions_exist(self):
        seoul = Region.objects.filter(code="seoul").first()
        incheon = Region.objects.filter(code="incheon").first()
        self.assertIsNotNone(seoul, "서울 Region 이 시드되어 있어야 합니다.")
        self.assertIsNotNone(incheon, "인천 Region 이 시드되어 있어야 합니다.")
        self.assertEqual(seoul.name, "서울")
        self.assertEqual(incheon.name, "인천")

    def test_all_existing_divisions_have_region(self):
        # 0009 백필 이후 region NOT NULL 이므로 null 인 부서가 0개여야 함.
        self.assertFalse(Division.objects.filter(region__isnull=True).exists())


class RegionScopePermissionsTests(TestCase):
    """region 인자가 *옵션*임을 검증 — 미지정 시 기존 동작 그대로."""

    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.incheon, _ = Region.objects.get_or_create(
            code="incheon", defaults={"name": "인천", "sort_order": 20}
        )
        # 서로 다른 지역에 부서 1개씩
        cls.seoul_div = Division.objects.create(
            region=cls.seoul, code="t_seoul_youth", name="청년부"
        )
        cls.incheon_div = Division.objects.create(
            region=cls.incheon, code="t_incheon_youth", name="청년부"
        )

        cls.superuser = User.objects.create_user(
            username="region_superuser",
            password="x",
            is_staff=True,
            is_superuser=True,
        )
        cls.user_seoul = User.objects.create_user(
            username="region_user_seoul", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.user_seoul, division=cls.seoul_div, is_primary=True
        )
        cls.user_incheon = User.objects.create_user(
            username="region_user_incheon", password="x"
        )
        UserDivisionTeam.objects.create(
            user=cls.user_incheon, division=cls.incheon_div, is_primary=True
        )

    def test_visible_divisions_default_unchanged_for_superuser(self):
        """region 미지정 = 슈퍼유저는 전체 부서(서울/인천 모두 포함)."""
        codes = set(
            visible_divisions_for(self.superuser).values_list("code", flat=True)
        )
        self.assertIn(self.seoul_div.code, codes)
        self.assertIn(self.incheon_div.code, codes)

    def test_visible_divisions_region_filter_narrows_superuser(self):
        codes = set(
            visible_divisions_for(self.superuser, region="seoul").values_list(
                "code", flat=True
            )
        )
        self.assertIn(self.seoul_div.code, codes)
        self.assertNotIn(self.incheon_div.code, codes)

    def test_visible_divisions_region_filter_accepts_instance(self):
        codes = set(
            visible_divisions_for(self.superuser, region=self.incheon).values_list(
                "code", flat=True
            )
        )
        self.assertEqual(codes, {self.incheon_div.code})

    def test_visible_divisions_region_filter_accepts_pk(self):
        codes = set(
            visible_divisions_for(self.superuser, region=self.seoul.pk).values_list(
                "code", flat=True
            )
        )
        self.assertIn(self.seoul_div.code, codes)
        self.assertNotIn(self.incheon_div.code, codes)

    def test_membership_divisions_default_unchanged(self):
        codes = list(
            membership_divisions_for(self.user_incheon).values_list("code", flat=True)
        )
        self.assertEqual(codes, [self.incheon_div.code])

    def test_membership_divisions_region_filter(self):
        # 인천 소속 유저에게 region='seoul' 지정 → 빈 쿼리셋
        qs = membership_divisions_for(self.user_incheon, region="seoul")
        self.assertEqual(list(qs), [])

    def test_dashboard_divisions_region_filter(self):
        codes = list(
            dashboard_divisions_for(self.user_seoul, region="incheon").values_list(
                "code", flat=True
            )
        )
        self.assertEqual(codes, [])

    def test_pastoral_divisions_default_for_normal_user_is_empty(self):
        # role_level 미지정 일반 유저는 빈 쿼리셋 (region 인자 영향 없음).
        self.assertEqual(list(pastoral_divisions_for(self.user_seoul)), [])

    def test_registry_divisions_default_for_normal_user_is_empty(self):
        self.assertEqual(list(registry_divisions_for(self.user_seoul)), [])

    def test_registry_divisions_superuser_region_filter(self):
        codes = set(
            registry_divisions_for(self.superuser, region="incheon").values_list(
                "code", flat=True
            )
        )
        self.assertIn(self.incheon_div.code, codes)
        self.assertNotIn(self.seoul_div.code, codes)

    def test_visible_regions_for_superuser_contains_seeded(self):
        codes = set(visible_regions_for(self.superuser).values_list("code", flat=True))
        self.assertIn("seoul", codes)
        self.assertIn("incheon", codes)

    def test_visible_regions_for_user_limited_to_own_division_regions(self):
        codes = set(
            visible_regions_for(self.user_incheon).values_list("code", flat=True)
        )
        self.assertEqual(codes, {"incheon"})
