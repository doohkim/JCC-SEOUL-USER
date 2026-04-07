"""
``예배 출석 명단.xlsx``(부서 회장단 + 팀 열) → 팀·멤버(Member)·부서 소속(MemberDivisionTeam).

기본 시트: ``주일 88``. 경로 생략 시 저장소 ``_test_rosters/2026/2026 예배 출석 명단.xlsx`` 를 우선 사용하고,
없으면 ``~/Downloads/2026 예배 출석 명단.xlsx`` 를 씁니다.

사용 (프로젝트 ``app/`` 에서):

  poetry run python manage.py seed_youth_roster --dry-run
  poetry run python manage.py seed_youth_roster "../_test_rosters/2026/2026 예배 출석 명단.xlsx"
  poetry run python manage.py seed_youth_roster --sheet "26.03.22 주일예배" --dry-run
  poetry run python manage.py seed_youth_roster --division-code youth
"""

from __future__ import annotations

import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from registry.importers.youth_roster_xlsx import (
    TEAM_SLUG,
    ascii_username_base,
    load_workbook_rows,
    parse_sheet,
)
from registry.models import Member, MemberDivisionTeam
from users.models import Division, Team

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_TEST_XLSX = _REPO_ROOT / "_test_rosters" / "2026" / "2026 예배 출석 명단.xlsx"
_DEFAULT_DOWNLOADS_XLSX = Path.home() / "Downloads" / "2026 예배 출석 명단.xlsx"


def _default_xlsx_path() -> Path:
    if _DEFAULT_TEST_XLSX.is_file():
        return _DEFAULT_TEST_XLSX
    return _DEFAULT_DOWNLOADS_XLSX


class Command(BaseCommand):
    help = "예배 출석 엑셀에서 청년부 팀·Member·소속을 생성합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "xlsx_path",
            nargs="?",
            type=str,
            default="",
            help="엑셀 경로 (생략 시 저장소 테스트 파일 또는 ~/Downloads/2026 예배 출석 명단.xlsx)",
        )
        parser.add_argument(
            "--sheet",
            default="주일 88",
            help="읽을 시트 이름 (기본: 주일 88)",
        )
        parser.add_argument(
            "--division-code",
            default="youth",
            help="부서 Division.code (기본: youth)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB에 쓰지 않고 파싱 결과만 출력",
        )

    def handle(self, *args, **options):
        raw_path = (options["xlsx_path"] or "").strip()
        path = (
            Path(raw_path).expanduser().resolve()
            if raw_path
            else _default_xlsx_path()
        )
        sheet_name = options["sheet"]
        division_code = (options["division_code"] or "youth").strip() or "youth"
        dry = options["dry_run"]

        if not path.is_file():
            raise CommandError(
                f"파일이 없습니다: {path}\n"
                f"경로를 지정하거나 {_DEFAULT_TEST_XLSX} / {_DEFAULT_DOWNLOADS_XLSX} 를 준비하세요."
            )

        try:
            rows = load_workbook_rows(path, sheet_name)
        except ImportError as e:
            raise CommandError(
                "openpyxl이 필요합니다. poetry install 또는 pip install openpyxl"
            ) from e
        except ValueError as e:
            raise CommandError(str(e)) from e

        try:
            team_cols, team_members = parse_sheet(rows)
        except ValueError as e:
            raise CommandError(str(e)) from e

        self.stdout.write(f"파일: {path}")
        self.stdout.write(f"시트: {sheet_name}, 부서 코드: {division_code}, 팀 열 {len(team_cols)}개")
        for tn, names in sorted(team_members.items()):
            self.stdout.write(f"  {tn}: {len(names)}명")

        if dry:
            self.stdout.write(self.style.WARNING("dry-run: DB 미반영"))
            return

        with transaction.atomic():
            div_defaults = {"name": "청년부", "sort_order": 10}
            if division_code != "youth":
                div_defaults = {"name": division_code, "sort_order": 10}
            div, _ = Division.objects.get_or_create(
                code=division_code,
                defaults=div_defaults,
            )
            if division_code == "youth" and div.name != "청년부":
                div.name = "청년부"
                div.save(update_fields=["name"])

            team_objs: dict[str, Team] = {}
            for order, (_, raw_name) in enumerate(team_cols):
                slug = TEAM_SLUG.get(raw_name)
                if not slug:
                    self.stdout.write(
                        self.style.WARNING(f"알 수 없는 팀명 스킵: {raw_name}")
                    )
                    continue
                t, _ = Team.objects.get_or_create(
                    division=div,
                    code=slug,
                    defaults={"name": raw_name, "sort_order": order},
                )
                if t.name != raw_name:
                    t.name = raw_name
                    t.sort_order = order
                    t.save(update_fields=["name", "sort_order"])
                team_objs[raw_name] = t

            used_ik: set[str] = set(
                Member.objects.exclude(import_key="").values_list("import_key", flat=True)
            )
            by_name: dict[str, Member] = {}
            for m in Member.objects.all():
                key = re.sub(r"\s+", "", (m.name or "").strip())
                if key:
                    by_name[key] = m

            created_members = 0
            links = 0

            for team_name, names in sorted(team_members.items()):
                team = team_objs.get(team_name)
                if not team:
                    continue
                for display in sorted(names):
                    key = re.sub(r"\s+", "", display)
                    member = by_name.get(key)
                    if member is None:
                        base = (ascii_username_base(display) or "member")[:64]
                        ik = base
                        n = 1
                        while ik in used_ik:
                            ik = f"{base}_{n}"[:64]
                            n += 1
                        used_ik.add(ik)
                        member = Member.objects.create(
                            name=display[:50],
                            import_key=ik,
                        )
                        by_name[key] = member
                        created_members += 1

                    mdt, created = MemberDivisionTeam.objects.get_or_create(
                        member=member,
                        division=div,
                        defaults={
                            "team": team,
                            "is_primary": not member.division_teams.filter(
                                division=div, is_primary=True
                            ).exists(),
                            "sort_order": 0,
                        },
                    )
                    if created:
                        links += 1
                    else:
                        if mdt.team_id != team.id:
                            mdt.team = team
                            mdt.save(update_fields=["team"])
                        if not member.division_teams.filter(
                            division=div, is_primary=True
                        ).exists():
                            mdt.is_primary = True
                            mdt.save(update_fields=["is_primary"])

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: Member 신규 {created_members}, 소속 링크 신규 {links} "
                f"(이미 있던 멤버는 팀만 추가)"
            )
        )
