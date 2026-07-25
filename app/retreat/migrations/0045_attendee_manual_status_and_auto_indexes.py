from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0044_attendee_travel_is_custom"),
    ]

    operations = [
        migrations.AddField(
            model_name="retreatattendee",
            name="check_in_status_manually_set",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "수동 상태를 자동 작업이 이전 단계로 되돌리지 않도록 구분합니다."
                ),
                verbose_name="입·퇴실 상태 수동 설정",
            ),
        ),
        migrations.AddIndex(
            model_name="retreatattendee",
            index=models.Index(
                fields=["expected_check_in_at"],
                name="idx_ret_att_expected_in",
            ),
        ),
        migrations.AddIndex(
            model_name="retreatattendee",
            index=models.Index(
                fields=["expected_check_out_at"],
                name="idx_ret_att_expected_out",
            ),
        ),
    ]
