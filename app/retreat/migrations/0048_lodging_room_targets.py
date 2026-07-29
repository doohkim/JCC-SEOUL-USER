import django.db.models.deletion
from django.db import migrations, models


def copy_legacy_room_scopes(apps, schema_editor):
    LodgingRoom = apps.get_model("retreat", "LodgingRoom")
    LodgingRoomScope = apps.get_model("retreat", "LodgingRoomScope")
    rows = [
        LodgingRoomScope(room_id=room.id, division_id=room.division_id)
        for room in LodgingRoom.objects.exclude(region_id=None).exclude(
            division_id=None
        )
        if room.division.region_id == room.region_id
    ]
    LodgingRoomScope.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0047_travel_preset_color"),
        ("users", "0012_preserve_profile_on_user_delete"),
    ]

    operations = [
        migrations.CreateModel(
            name="LodgingRoomScope",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "division",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retreat_lodging_room_scopes",
                        to="users.division",
                        verbose_name="부서",
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scopes",
                        to="retreat.lodgingroom",
                        verbose_name="호실",
                    ),
                ),
            ],
            options={
                "verbose_name": "수련회 호실 지역·부서 범위",
                "verbose_name_plural": "수련회 호실 지역·부서 범위",
                "ordering": [
                    "room",
                    "division__region__sort_order",
                    "division__sort_order",
                    "id",
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("room", "division"),
                        name="uniq_lodging_room_scope_room_division",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="LodgingRoomGroupTarget",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lodging_room_targets",
                        to="retreat.retreatgroup",
                        verbose_name="조",
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_targets",
                        to="retreat.lodgingroom",
                        verbose_name="호실",
                    ),
                ),
            ],
            options={
                "verbose_name": "수련회 호실 지정 조",
                "verbose_name_plural": "수련회 호실 지정 조",
                "ordering": ["room", "group__order", "group__id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("room", "group"),
                        name="uniq_lodging_room_group_target",
                    )
                ],
            },
        ),
        migrations.RunPython(copy_legacy_room_scopes, migrations.RunPython.noop),
    ]
