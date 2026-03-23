"""교적 변경 → 연결된 User 조직 소속 동기화."""

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from registry.models import Member, MemberDivisionTeam
from registry.services.linked_user_org_sync import sync_user_division_teams_from_member
from users.models.organization import Team


@receiver(post_save, sender=MemberDivisionTeam)
def member_division_team_saved(sender, instance: MemberDivisionTeam, **kwargs):
    if kwargs.get("raw"):
        return
    sync_user_division_teams_from_member(instance.member)


@receiver(post_delete, sender=MemberDivisionTeam)
def member_division_team_deleted(sender, instance: MemberDivisionTeam, **kwargs):
    member = Member.objects.filter(pk=instance.member_id).first()
    if member is not None:
        sync_user_division_teams_from_member(member)


@receiver(post_delete, sender=Team)
def team_deleted_compact_member_division_team_rows(sender, instance: Team, **kwargs):
    """
    팀 삭제 시 SET_NULL(on_delete)로 인해 member/division 별로
    team=None 행이 여러 개 생길 수 있다.
    - member/division 당 1행만 남기고
    - is_primary도 1개만 유지한다.
    """
    division_id = instance.division_id
    if not division_id:
        return

    with transaction.atomic():
        base_qs = MemberDivisionTeam.objects.filter(
            division_id=division_id,
            team__isnull=True,
        ).select_related("member")

        member_ids = base_qs.values_list("member_id", flat=True).distinct()
        for mid in member_ids:
            rows = list(
                base_qs.filter(member_id=mid).order_by(
                    "-is_primary",
                    "sort_order",
                    "id",
                )
            )
            if len(rows) <= 1:
                continue
            keep = rows[0]
            # keep 행이 primary가 아니면 primary를 keep로 이동
            if not keep.is_primary:
                for r in rows:
                    r.is_primary = (r.pk == keep.pk)
                    r.save(update_fields=["is_primary"])

            # 나머지 중복 행 삭제
            to_delete_ids = [r.pk for r in rows[1:]]
            MemberDivisionTeam.objects.filter(pk__in=to_delete_ids).delete()


@receiver(post_save, sender=Member)
def member_saved_sync_linked_user_org(sender, instance: Member, **kwargs):
    """연결 계정이 있으면 교적 소속을 User 쪽에 맞춘다(연결 직후·이름만 수정 등에도 idempotent)."""
    if kwargs.get("raw"):
        return
    if instance.linked_user_id:
        sync_user_division_teams_from_member(instance)
