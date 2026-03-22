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
            ("전도사", "evangelist", 80),
            ("부장", "dept_head", 60),
            ("일반", "member", 0),
        ]
        for name_ko, code, level in levels:
            RoleLevel.objects.get_or_create(
                code=code,
                defaults={"name": name_ko, "level": level, "sort_order": 100 - level},
            )
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
            ("회장", "president", 10),
            ("부회장", "vice_president", 11),
            ("총무", "secretary_general", 12),
            ("서기", "secretary", 13),
            ("담당 목사", "pastor_in_charge", 1),
            ("간사", "coordinator", 20),
            ("부장", "dept_head", 21),
            ("차장", "deputy_head", 22),
            ("기획편집국", "planning_editor", 23),
            ("단장", "praise_leader", 30),
            ("부단장", "praise_deputy", 31),
            ("리더", "praise_leader_role", 32),
            ("고문", "advisor", 33),
            ("기악팀장", "instrumental_leader", 34),
            ("워십팀장", "worship_leader", 35),
            ("지역장", "region_leader", 40),
            ("팀장", "team_leader", 41),
            ("셀장", "cell_leader", 42),
        ]
        for name_ko, code, order in roles:
            Role.objects.get_or_create(
                code=code, defaults={"name": name_ko, "sort_order": order}
            )
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
