"""
조직도 시드: 상위 부서(Division), 직급(RoleLevel), 직책(Role), 일하는 부서(FunctionalDepartment) 등.
실행: python manage.py seed_org_chart
"""
from django.core.management.base import BaseCommand

from users.models import Division, FunctionalDepartment, Role, RoleLevel


class Command(BaseCommand):
    help = "교회 조직도 초기 데이터 생성 (상위 부서, 직급, 직책, 일하는 부서)"

    def handle(self, *args, **options):
        self._seed_role_levels()
        self._seed_divisions()
        self._seed_roles()
        self._seed_functional_departments()
        self.stdout.write(self.style.SUCCESS("조직도 시드 완료."))

    def _seed_role_levels(self):
        levels = [
            ("목사", "pastor", 100),
            ("전도사", "evangelist", 90),
            ("회장", "president", 80),
            ("부회장", "vice_president", 70),
            ("총무", "secretary_general", 60),
            ("팀장", "team_leader", 50),
            ("셀장", "cell_leader", 40),
            ("팀원", "team_member", 10),
        ]
        for name_ko, code, level in levels:
            obj, _ = RoleLevel.objects.get_or_create(
                code=code,
                defaults={"name": name_ko, "level": level, "sort_order": 100 - level},
            )
            updates = []
            if obj.name != name_ko:
                obj.name = name_ko
                updates.append("name")
            if obj.level != level:
                obj.level = level
                updates.append("level")
            target_sort = 100 - level
            if obj.sort_order != target_sort:
                obj.sort_order = target_sort
                updates.append("sort_order")
            if updates:
                obj.save(update_fields=updates)
        self.stdout.write(f"  RoleLevel {len(levels)}개 생성/유지")

    def _seed_divisions(self):
        divisions = [
            ("청년부", "youth", 10),
            ("대학부", "university", 20),
            ("중고등부", "middle_high", 30),
            ("철산 교구", "cheolsan", 40),
            ("동작 교구", "dongjak", 50),
        ]
        for name_ko, code, sort_order in divisions:
            obj, created = Division.objects.get_or_create(
                code=code,
                defaults={"name": name_ko, "sort_order": sort_order},
            )
            if not created and obj.sort_order != sort_order:
                obj.sort_order = sort_order
                obj.save(update_fields=["sort_order"])
        self.stdout.write(f"  Division {len(divisions)}개 생성/유지")

    def _seed_roles(self):
        roles = [
            ("부장", "dept_head", 10),
            ("차장", "deputy_dept_head", 11),
            ("간사", "secretary", 12),
            ("기악장", "instrument_leader", 13),
            ("워십장", "worship_leader", 14),
            ("단장", "choir_leader", 15),
            ("부단장", "vice_choir_leader", 16),
            ("리더", "leader", 17),
        ]
        for name_ko, code, order in roles:
            obj, _ = Role.objects.get_or_create(
                code=code,
                defaults={"name": name_ko, "sort_order": order},
            )
            updates = []
            if obj.name != name_ko:
                obj.name = name_ko
                updates.append("name")
            if obj.sort_order != order:
                obj.sort_order = order
                updates.append("sort_order")
            if updates:
                obj.save(update_fields=updates)
        self.stdout.write(f"  Role {len(roles)}개 생성/유지")

    def _seed_functional_departments(self):
        # division=null → 교회 전체 부서
        depts = [
            ("찬양단", "praise", None),
            ("전도부", "evangelism", None),
            ("멀티미디어부", "multimedia", None),
            ("새가족부", "newcomer", None),
            ("구제교남복지", "relief_welfare", None),
        ]
        for name_ko, code, division in depts:
            FunctionalDepartment.objects.get_or_create(
                code=code,
                defaults={"name": name_ko, "division": division, "sort_order": 0},
            )
        self.stdout.write(f"  FunctionalDepartment {len(depts)}개 생성/유지")
