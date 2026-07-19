# Generated manually for retreat session snapshots.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0006_normalize_attendance_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="retreatsession",
            name="status",
            field=models.CharField(
                choices=[("active", "진행중"), ("closed", "마감")],
                default="active",
                max_length=10,
                verbose_name="상태",
            ),
        ),
        migrations.AddField(
            model_name="retreatsession",
            name="closed_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="마감 일시",
            ),
        ),
        migrations.AddField(
            model_name="retreatsession",
            name="closed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="retreat_sessions_closed",
                to=settings.AUTH_USER_MODEL,
                verbose_name="마감자",
            ),
        ),
        migrations.CreateModel(
            name="RetreatSessionAttendee",
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
                ("name", models.CharField(max_length=60, verbose_name="이름")),
                (
                    "phone",
                    models.CharField(
                        blank=True, default="", max_length=30, verbose_name="연락처"
                    ),
                ),
                (
                    "gender",
                    models.CharField(
                        blank=True,
                        choices=[("male", "남성"), ("female", "여성"), ("", "미지정")],
                        default="",
                        max_length=10,
                        verbose_name="성별",
                    ),
                ),
                (
                    "memo",
                    models.CharField(
                        blank=True, default="", max_length=200, verbose_name="메모"
                    ),
                ),
                (
                    "check_in_status",
                    models.CharField(
                        choices=[("checked_in", "입실"), ("checked_out", "퇴실")],
                        default="checked_in",
                        max_length=15,
                        verbose_name="입·퇴실",
                    ),
                ),
                ("group_name", models.CharField(max_length=50, verbose_name="조 이름")),
                (
                    "region_id_snapshot",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="지역 ID"
                    ),
                ),
                (
                    "region_name",
                    models.CharField(
                        blank=True, default="", max_length=100, verbose_name="지역명"
                    ),
                ),
                (
                    "division_id_snapshot",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="부서 ID"
                    ),
                ),
                (
                    "division_name",
                    models.CharField(
                        blank=True, default="", max_length=100, verbose_name="부서명"
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveSmallIntegerField(
                        default=0, verbose_name="정렬 순서"
                    ),
                ),
                (
                    "enrolled_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="스냅샷 생성 일시"
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="enrollments",
                        to="retreat.retreatsession",
                        verbose_name="출석부",
                    ),
                ),
                (
                    "source_attendee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="session_enrollments",
                        to="retreat.retreatattendee",
                        verbose_name="원본 조원",
                    ),
                ),
                (
                    "source_group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="session_enrollments",
                        to="retreat.retreatgroup",
                        verbose_name="원본 조",
                    ),
                ),
            ],
            options={
                "verbose_name": "수련회 출석부 조원 스냅샷",
                "verbose_name_plural": "수련회 출석부 조원 스냅샷",
                "ordering": [
                    "session",
                    "region_id_snapshot",
                    "division_id_snapshot",
                    "sort_order",
                    "name",
                    "id",
                ],
            },
        ),
        migrations.AddField(
            model_name="retreatattendance",
            name="enrollment",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="attendance",
                to="retreat.retreatsessionattendee",
                verbose_name="출석부 조원",
            ),
        ),
        migrations.AddConstraint(
            model_name="retreatsessionattendee",
            constraint=models.UniqueConstraint(
                fields=("session", "source_attendee"),
                name="uniq_retreat_session_attendee_source",
            ),
        ),
        migrations.AddIndex(
            model_name="retreatsessionattendee",
            index=models.Index(
                fields=["session", "source_group", "sort_order"],
                name="idx_ret_enroll_sess_group",
            ),
        ),
        migrations.AddIndex(
            model_name="retreatsessionattendee",
            index=models.Index(
                fields=["session", "region_id_snapshot", "division_id_snapshot"],
                name="idx_ret_enroll_sess_div",
            ),
        ),
    ]
