"""RetreatAttendee.check_in_status 에 '입실전(pending)' 추가 + default 변경."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0011_attendee_check_in_timestamps"),
    ]

    operations = [
        migrations.AlterField(
            model_name="retreatattendee",
            name="check_in_status",
            field=models.CharField(
                choices=[
                    ("checked_in", "입실"),
                    ("checked_out", "퇴실"),
                    ("pending", "입실전"),
                ],
                default="pending",
                help_text="입실전·퇴실 상태인 조원은 출석부에서 결석이 기본으로 선택됩니다.",
                max_length=15,
                verbose_name="입·퇴실",
            ),
        ),
        migrations.AlterField(
            model_name="retreatsessionattendee",
            name="check_in_status",
            field=models.CharField(
                choices=[
                    ("checked_in", "입실"),
                    ("checked_out", "퇴실"),
                    ("pending", "입실전"),
                ],
                default="checked_in",
                max_length=15,
                verbose_name="입·퇴실",
            ),
        ),
    ]
