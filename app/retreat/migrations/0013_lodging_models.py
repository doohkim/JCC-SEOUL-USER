"""Lodging / LodgingRoom 모델 생성 및 RetreatAttendee.lodging_room FK 추가."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0012_attendee_pending_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="Lodging",
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
                ("name", models.CharField(max_length=80, verbose_name="숙소명")),
                (
                    "address",
                    models.CharField(
                        blank=True, default="", max_length=200, verbose_name="주소"
                    ),
                ),
                (
                    "memo",
                    models.CharField(
                        blank=True, default="", max_length=200, verbose_name="메모"
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveSmallIntegerField(
                        default=0, verbose_name="정렬 순서"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="lodgings",
                        to="retreat.retreatevent",
                        verbose_name="행사",
                    ),
                ),
            ],
            options={
                "verbose_name": "수련회 숙소",
                "verbose_name_plural": "수련회 숙소",
                "ordering": ["event", "sort_order", "name", "id"],
            },
        ),
        migrations.CreateModel(
            name="LodgingRoom",
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
                ("number", models.CharField(max_length=30, verbose_name="호수")),
                (
                    "capacity",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="0 = 정원 무제한",
                        verbose_name="정원",
                    ),
                ),
                (
                    "recommended_gender",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("male", "남성"),
                            ("female", "여성"),
                            ("mixed", "혼성"),
                            ("", "미지정"),
                        ],
                        default="",
                        max_length=10,
                        verbose_name="권장 성별",
                    ),
                ),
                (
                    "memo",
                    models.CharField(
                        blank=True, default="", max_length=200, verbose_name="메모"
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveSmallIntegerField(
                        default=0, verbose_name="정렬 순서"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "lodging",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="rooms",
                        to="retreat.lodging",
                        verbose_name="숙소",
                    ),
                ),
            ],
            options={
                "verbose_name": "수련회 호실",
                "verbose_name_plural": "수련회 호실",
                "ordering": ["lodging", "sort_order", "number", "id"],
            },
        ),
        migrations.AddField(
            model_name="retreatattendee",
            name="lodging_room",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="attendees",
                to="retreat.lodgingroom",
                verbose_name="숙소 호실",
            ),
        ),
        migrations.AddConstraint(
            model_name="lodging",
            constraint=models.UniqueConstraint(
                fields=("event", "name"),
                name="uniq_retreat_lodging_event_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="lodgingroom",
            constraint=models.UniqueConstraint(
                fields=("lodging", "number"),
                name="uniq_retreat_lodging_room_number",
            ),
        ),
    ]
