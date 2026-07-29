from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0049_alter_lodging_room_gender_label"),
    ]

    operations = [
        migrations.AlterField(
            model_name="retreatchangelog",
            name="action",
            field=models.CharField(
                choices=[
                    ("create", "생성"),
                    ("update", "수정"),
                    ("delete", "삭제"),
                    ("approve", "승인"),
                    ("reject", "반려"),
                ],
                max_length=10,
                verbose_name="동작",
            ),
        ),
        migrations.AlterField(
            model_name="retreatchangelog",
            name="target_type",
            field=models.CharField(
                choices=[
                    ("session", "출석부"),
                    ("attendee", "조원"),
                    ("enrollment", "출석부 조원"),
                    ("attendance", "출석"),
                    ("group_membership", "조 운영진"),
                    ("group", "조"),
                    ("pickup", "픽업"),
                    ("pickup_location", "탑승장소"),
                    ("timetable", "타임테이블"),
                    ("staff_application", "운영진 신청"),
                ],
                max_length=30,
                verbose_name="대상 유형",
            ),
        ),
    ]
