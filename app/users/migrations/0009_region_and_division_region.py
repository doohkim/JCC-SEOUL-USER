"""Region 도입 + Division.region FK 추가.

1. Region 모델 신설
2. Division.region (nullable) 추가
3. Region "서울"/"인천" 시드 + 기존 Division 전부 서울로 백필
4. Division.region NOT NULL 로 변경
"""

import django.db.models.deletion
from django.db import migrations, models


REGION_SPECS = [
    ("seoul", "서울", 10),
    ("incheon", "인천", 20),
]


def seed_and_backfill(apps, schema_editor):
    Region = apps.get_model("users", "Region")
    Division = apps.get_model("users", "Division")

    region_by_code: dict[str, "Region"] = {}
    for idx, (code, name, sort_order) in enumerate(REGION_SPECS):
        obj, _ = Region.objects.get_or_create(
            code=code,
            defaults={"name": name, "sort_order": sort_order},
        )
        updates = []
        if obj.name != name:
            obj.name = name
            updates.append("name")
        if obj.sort_order != sort_order:
            obj.sort_order = sort_order
            updates.append("sort_order")
        if updates:
            obj.save(update_fields=updates)
        region_by_code[code] = obj

    seoul = region_by_code["seoul"]
    Division.objects.filter(region__isnull=True).update(region=seoul)


def remove_seeded_regions(apps, schema_editor):
    """역마이그레이션: Division.region 을 null 로 비우는 단계는 다음 RemoveField 가 처리.
    Region 행은 보존(다른 FK 가 생겼을 가능성 보호)."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_external_service_client"),
    ]

    operations = [
        migrations.CreateModel(
            name="Region",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50, verbose_name="이름")),
                (
                    "code",
                    models.SlugField(max_length=30, unique=True, verbose_name="코드"),
                ),
                (
                    "sort_order",
                    models.PositiveSmallIntegerField(
                        default=0, verbose_name="정렬 순서"
                    ),
                ),
            ],
            options={
                "verbose_name": "지역",
                "verbose_name_plural": "지역",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="division",
            name="region",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="divisions",
                to="users.region",
                verbose_name="지역",
            ),
        ),
        migrations.RunPython(seed_and_backfill, remove_seeded_regions),
        migrations.AlterField(
            model_name="division",
            name="region",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="divisions",
                to="users.region",
                verbose_name="지역",
            ),
        ),
        migrations.AlterModelOptions(
            name="division",
            options={
                "ordering": ["region__sort_order", "sort_order", "name"],
                "verbose_name": "상위 부서",
                "verbose_name_plural": "상위 부서",
            },
        ),
    ]
