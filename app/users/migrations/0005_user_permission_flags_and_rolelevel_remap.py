from django.db import migrations, models


ROLE_LEVEL_SPECS = [
    ("pastor", "목사", 100),
    ("evangelist", "전도사", 90),
    ("president", "회장", 80),
    ("vice_president", "부회장", 70),
    ("secretary_general", "총무", 60),
    ("team_leader", "팀장", 50),
    ("cell_leader", "셀장", 40),
    ("team_member", "팀원", 10),
]

ROLE_LEVEL_MAP = {
    "pastor": "pastor",
    "evangelist": "evangelist",
    "president": "president",
    "vice_president": "vice_president",
    "secretary_general": "secretary_general",
    "team_leader": "team_leader",
    "cell_leader": "cell_leader",
    "member": "team_member",
    "dept_head": "team_leader",
}


def forwards(apps, schema_editor):
    RoleLevel = apps.get_model("users", "RoleLevel")
    User = apps.get_model("users", "User")
    UserFunctionalDeptRole = apps.get_model("users", "UserFunctionalDeptRole")

    rolelevel_by_code = {}
    for idx, (code, name, level) in enumerate(ROLE_LEVEL_SPECS):
        obj, _ = RoleLevel.objects.get_or_create(
            code=code,
            defaults={"name": name, "level": level, "sort_order": idx},
        )
        updates = []
        if obj.name != name:
            obj.name = name
            updates.append("name")
        if obj.level != level:
            obj.level = level
            updates.append("level")
        if obj.sort_order != idx:
            obj.sort_order = idx
            updates.append("sort_order")
        if updates:
            obj.save(update_fields=updates)
        rolelevel_by_code[code] = obj

    fallback = rolelevel_by_code["team_member"]
    users = User.objects.select_related("role_level").all()
    for u in users:
        cur_code = getattr(getattr(u, "role_level", None), "code", None)
        target_code = ROLE_LEVEL_MAP.get(cur_code, "team_member")
        target = rolelevel_by_code.get(target_code, fallback)
        updates = []
        if u.role_level_id != target.id:
            u.role_level_id = target.id
            updates.append("role_level")
        # legacy role code -> 기능권한 플래그 이관
        role_codes = set(
            UserFunctionalDeptRole.objects.filter(user_id=u.id).values_list("role__code", flat=True)
        )
        attendance = "attendance_admin" in role_codes
        parking = "parking_admin" in role_codes
        account = "account_admin" in role_codes
        if u.can_manage_attendance != attendance:
            u.can_manage_attendance = attendance
            updates.append("can_manage_attendance")
        if u.can_manage_parking != parking:
            u.can_manage_parking = parking
            updates.append("can_manage_parking")
        if u.can_manage_accounts != account:
            u.can_manage_accounts = account
            updates.append("can_manage_accounts")
        if updates:
            u.save(update_fields=updates)


def backwards(apps, schema_editor):
    # flags/새 직급체계 도입 이전으로 정확한 복원은 불가
    return


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_userdivisionteam_one_team_per_division"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="can_manage_accounts",
            field=models.BooleanField(
                default=False,
                help_text="부서 계정 직책 관리 화면 접근 권한",
                verbose_name="계정 관리 권한",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="can_manage_attendance",
            field=models.BooleanField(
                default=False,
                help_text="팀장 출석/출석부 관리 화면 접근 권한",
                verbose_name="출석 관리 권한",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="can_manage_parking",
            field=models.BooleanField(
                default=False,
                help_text="주차권/주차 운영 관리 화면 접근 권한",
                verbose_name="주차 관리 권한",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
