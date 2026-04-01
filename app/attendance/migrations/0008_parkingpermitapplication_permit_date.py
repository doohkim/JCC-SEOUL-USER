# Generated manually for permit_date (KST calendar day) + unique per day

from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_permit_date(apps, schema_editor):
    KST = ZoneInfo("Asia/Seoul")
    ParkingPermitApplication = apps.get_model("attendance", "ParkingPermitApplication")
    for row in ParkingPermitApplication.objects.all().iterator():
        if row.created_at:
            d = row.created_at.astimezone(KST).date()
        else:
            d = timezone.now().astimezone(KST).date()
        row.permit_date = d
        row.save(update_fields=["permit_date"])


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0007_parkingpermitapplication"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="parkingpermitapplication",
            name="unique_user_vehicle_number",
        ),
        migrations.AddField(
            model_name="parkingpermitapplication",
            name="permit_date",
            field=models.DateField(
                db_index=True,
                help_text="한국 달력 기준 하루 1회 신청을 구분하는 날짜입니다.",
                null=True,
                verbose_name="등록 기준일(한국)",
            ),
        ),
        migrations.RunPython(backfill_permit_date, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="parkingpermitapplication",
            name="permit_date",
            field=models.DateField(
                db_index=True,
                help_text="한국 달력 기준 하루 1회 신청을 구분하는 날짜입니다.",
                verbose_name="등록 기준일(한국)",
            ),
        ),
        migrations.AddConstraint(
            model_name="parkingpermitapplication",
            constraint=models.UniqueConstraint(
                fields=("user", "vehicle_number", "permit_date"),
                name="unique_user_vehicle_permit_date",
            ),
        ),
        migrations.AlterModelOptions(
            name="parkingpermitapplication",
            options={
                "ordering": ["-permit_date", "-created_at"],
                "verbose_name": "주차권 신청",
                "verbose_name_plural": "주차권 신청",
            },
        ),
    ]
