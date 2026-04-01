# ParkingPermitWindow — 부서별 요일·시간대

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0008_parkingpermitapplication_permit_date"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParkingPermitWindow",
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
                (
                    "weekday",
                    models.SmallIntegerField(
                        choices=[
                            (0, "월"),
                            (1, "화"),
                            (2, "수"),
                            (3, "목"),
                            (4, "금"),
                            (5, "토"),
                            (6, "일"),
                        ],
                        help_text="월=0 … 일=6 (한국 시각 기준 요일과 동일)",
                        verbose_name="요일",
                    ),
                ),
                ("start_time", models.TimeField(verbose_name="시작 시각")),
                ("end_time", models.TimeField(verbose_name="종료 시각")),
                ("is_active", models.BooleanField(default=True, verbose_name="사용")),
                (
                    "division",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parking_permit_windows",
                        to="users.division",
                        verbose_name="부서",
                    ),
                ),
            ],
            options={
                "verbose_name": "주차권 신청 가능 시간",
                "verbose_name_plural": "주차권 신청 가능 시간",
                "ordering": ["division", "weekday", "start_time"],
            },
        ),
        migrations.AddIndex(
            model_name="parkingpermitwindow",
            index=models.Index(
                fields=["division", "weekday", "is_active"],
                name="attendance_p_division_2f4c8e_idx",
            ),
        ),
    ]
