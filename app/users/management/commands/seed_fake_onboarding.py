"""
가입신청서 UI 확인용 데모 신청자 (로컬 전용).

생성::

    python manage.py seed_fake_onboarding
    python manage.py seed_fake_onboarding --count 30

삭제 (username ``fake_onboard_`` 접두사 계정·프로필 전부)::

    python manage.py seed_fake_onboarding --purge
"""

from __future__ import annotations

import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from users.models import Division, Team, UserProfile

FAKE_USERNAME_PREFIX = "fake_onboard_"

SAMPLE_NAMES = [
    "김민준",
    "이서연",
    "박지후",
    "최유나",
    "정도윤",
    "강하은",
    "조시우",
    "윤지민",
    "장예준",
    "임수아",
    "한지호",
    "오서윤",
    "신민재",
    "권다은",
    "황준서",
    "송채원",
    "백현우",
    "남소율",
    "문태양",
    "양지우",
    "구민성",
    "노하린",
    "류건우",
    "탁서현",
    "피지안",
    "설은우",
    "표나연",
    "길도현",
    "마채린",
    "반시윤",
]

User = get_user_model()


class Command(BaseCommand):
    help = "가입신청서 확인용 데모 신청자 생성/삭제 (fake_onboard_* 계정)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=30,
            help="생성할 데모 신청자 수 (기본 30)",
        )
        parser.add_argument(
            "--purge",
            action="store_true",
            help="fake_onboard_* 계정과 연결 프로필을 모두 삭제",
        )

    def handle(self, *args, **options):
        if options["purge"]:
            self._purge()
            return
        count = options["count"]
        if count < 1:
            raise CommandError("--count 는 1 이상이어야 합니다.")
        created = self._seed(count)
        self.stdout.write(
            self.style.SUCCESS(
                f"데모 가입신청 {created}건 생성 완료 (username 접두사: {FAKE_USERNAME_PREFIX})"
            )
        )
        self.stdout.write(
            "삭제: python manage.py seed_fake_onboarding --purge"
        )

    @transaction.atomic
    def _purge(self) -> None:
        user_qs = User.objects.filter(username__startswith=FAKE_USERNAME_PREFIX)
        user_count = user_qs.count()
        profile_count = UserProfile.objects.filter(user__in=user_qs).count()
        UserProfile.objects.filter(user__in=user_qs).delete()
        user_qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"데모 계정 {user_count}명·프로필 {profile_count}건 삭제 완료"
            )
        )

    @transaction.atomic
    def _seed(self, count: int) -> int:
        divisions = list(
            Division.objects.select_related("region").order_by(
                "region__sort_order", "sort_order", "name"
            )
        )
        if not divisions:
            raise CommandError("부서(Division)가 없습니다. seed_org_chart 등을 먼저 실행하세요.")

        teams_by_div: dict[int, list[Team]] = {}
        for team in Team.objects.select_related("division").order_by("sort_order", "name"):
            teams_by_div.setdefault(team.division_id, []).append(team)

        retreat_event = None
        retreat_groups_by_div: dict[int, list] = {}
        try:
            from retreat.models import RetreatEvent, RetreatGroup

            retreat_event = (
                RetreatEvent.objects.filter(is_active=True).order_by("-start_date").first()
            )
            if retreat_event:
                for group in RetreatGroup.objects.filter(event=retreat_event).order_by(
                    "name"
                ):
                    retreat_groups_by_div.setdefault(group.division_id, []).append(group)
        except Exception:
            retreat_event = None

        existing = set(
            User.objects.filter(username__startswith=FAKE_USERNAME_PREFIX).values_list(
                "username", flat=True
            )
        )

        statuses = (
            [UserProfile.OnboardingStatus.PENDING] * 22
            + [UserProfile.OnboardingStatus.APPROVED] * 4
            + [UserProfile.OnboardingStatus.REJECTED] * 4
        )
        random.shuffle(statuses)

        created = 0
        now = timezone.now()
        for i in range(1, count + 1):
            username = f"{FAKE_USERNAME_PREFIX}{i:02d}"
            if username in existing:
                continue

            division = divisions[(i - 1) % len(divisions)]
            teams = teams_by_div.get(division.id) or []
            team = teams[(i - 1) % len(teams)] if teams else None
            real_name = SAMPLE_NAMES[(i - 1) % len(SAMPLE_NAMES)]
            if i > len(SAMPLE_NAMES):
                real_name = f"{real_name}{i - len(SAMPLE_NAMES)}"

            user = User.objects.create_user(
                username=username,
                password="fake-onboard-demo",
                is_active=True,
            )
            profile = UserProfile.objects.create(
                user=user,
                real_name=real_name,
                phone=f"010-90{i:02d}-{(1000 + i):04d}",
            )
            profile.onboarding_status = statuses[(i - 1) % len(statuses)]
            profile.onboarding_note = (
                "데모 반려 사유" if profile.onboarding_status == UserProfile.OnboardingStatus.REJECTED else ""
            )
            profile.requested_division = division
            profile.requested_team = team

            groups = retreat_groups_by_div.get(division.id) or []
            if retreat_event and groups and i % 3 != 0:
                profile.requested_retreat_participation = True
                profile.requested_retreat_event = retreat_event
                profile.requested_retreat_group = groups[(i - 1) % len(groups)]
            else:
                profile.requested_retreat_participation = False
                profile.requested_retreat_event = None
                profile.requested_retreat_group = None

            profile.updated_at = now - timezone.timedelta(hours=i)
            profile.save()
            created += 1

        return created
