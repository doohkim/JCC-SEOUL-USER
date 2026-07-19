"""
폴더 아래의 예배 출석 엑셀(동일 포맷)을 읽어 Member·청년부 팀 소속과
``WorshipRosterScope`` / ``WorshipRosterEntry`` 에 반영합니다.

경로에서 연도·예배 구분·부를 추론합니다.

- **인천**: 경로에 1~4부가 없으면 **3부**로 저장.
- **서울**: 경로에 ``1부``~``4부`` (또는 ``1bu`` 등) 가 있어야 합니다.
- **온라인 / 지교회**: ``session_part`` = 0 (부 해당 없음). 지교회는 ``지교회/○○/파일.xlsx`` 의 ○○을 ``branch_label`` 로 사용.

시트:

- 기본: ``주일 88`` 시트만 (없으면 워크북에서 **첫 번째** 파싱 가능 시트 1개만).
- ``--single-sheet "이름"``: 해당 시트만.
- ``--all-sheets``: 파싱 가능한 **모든** 시트를 각각 별도 구분(``snapshot_label``)으로 저장.

사용 예::

    python manage.py import_youth_attendance_rosters /path/to/rosters
    python manage.py import_youth_attendance_rosters /path/to/rosters --dry-run
    python manage.py import_youth_attendance_rosters /path/to/rosters --division-code youth
    python manage.py import_youth_attendance_rosters /path/to/rosters --all-sheets
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("registry.import")

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from attendance.models import WorshipRosterEntry, WorshipRosterScope
from registry.importers.roster_path_context import infer_roster_path_context
from registry.importers.youth_roster_xlsx import (
    TEAM_SLUG,
    ascii_username_base,
    iter_parseable_sheets,
    parse_sheet,
)
from registry.models import Member, MemberDivisionTeam
from users.models import Division, Team


class Command(BaseCommand):
    help = "폴더 내 출석 엑셀을 연도·예배구분·부별로 임포트합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "root",
            type=str,
            help="엑셀들이 들어 있는 루트 폴더",
        )
        parser.add_argument(
            "--division-code",
            default="youth",
            help="청년부 Division code (기본: youth)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB에 쓰지 않고 파싱·추론 결과만 출력",
        )
        parser.add_argument(
            "--preferred-sheet",
            default="주일 88",
            help="기본 모드에서 우선 사용할 시트명 (없으면 첫 파싱 가능 시트)",
        )
        parser.add_argument(
            "--single-sheet",
            type=str,
            default="",
            help="지정 시 이 시트만 읽음 (--preferred-sheet·--all-sheets보다 우선)",
        )
        parser.add_argument(
            "--all-sheets",
            action="store_true",
            help="파싱 가능한 모든 시트를 시트명으로 snapshot_label 구분하여 저장",
        )

    def handle(self, *args, **options):
        root = Path(options["root"]).expanduser().resolve()
        division_code = options["division_code"]
        dry = options["dry_run"]
        single_sheet = (options["single_sheet"] or "").strip()
        preferred_sheet = (options["preferred_sheet"] or "").strip() or "주일 88"
        all_sheets_mode = bool(options["all_sheets"]) and not single_sheet

        if not root.is_dir():
            raise CommandError(f"폴더가 아닙니다: {root}")

        try:
            import openpyxl
        except ImportError as e:
            raise CommandError(
                "openpyxl이 필요합니다. poetry install 또는 pip install openpyxl"
            ) from e

        xlsx_files = sorted(root.rglob("*.xlsx"))
        # 임시/숨김 제외
        xlsx_files = [
            p for p in xlsx_files if not p.name.startswith("~$") and "/." not in str(p)
        ]

        if not xlsx_files:
            raise CommandError(f"xlsx 파일이 없습니다: {root}")

        self.stdout.write(f"대상 파일 {len(xlsx_files)}개 (루트: {root})")

        parsed_files: list[tuple[Path, object, dict]] = []
        skipped = 0

        for path in xlsx_files:
            rel = path.relative_to(root)
            ctx = infer_roster_path_context(rel)
            if ctx is None:
                self.stdout.write(self.style.WARNING(f"경로 추론 실패(스킵): {rel}"))
                skipped += 1
                continue

            if single_sheet:
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                if single_sheet not in wb.sheetnames:
                    wb.close()
                    self.stdout.write(
                        self.style.WARNING(f"시트 없음(스킵): {rel} → '{single_sheet}'")
                    )
                    skipped += 1
                    continue
                ws = wb[single_sheet]
                rows = list(ws.iter_rows(values_only=True))
                wb.close()
                try:
                    team_cols, team_members = parse_sheet(rows)
                except ValueError as e:
                    self.stdout.write(
                        self.style.WARNING(f"파싱 실패(스킵): {rel} — {e}")
                    )
                    skipped += 1
                    continue
                sheets_data = {single_sheet: (team_cols, team_members)}
            else:
                sheets_data = iter_parseable_sheets(path)
                if not sheets_data:
                    self.stdout.write(
                        self.style.WARNING(
                            f"읽을 시트 없음(스킵): {rel} (부서 회장단 포맷?)"
                        )
                    )
                    skipped += 1
                    continue
                if not all_sheets_mode:
                    if preferred_sheet in sheets_data:
                        sheets_data = {preferred_sheet: sheets_data[preferred_sheet]}
                    else:
                        first_sn = next(iter(sheets_data))
                        sheets_data = {first_sn: sheets_data[first_sn]}
                        self.stdout.write(
                            self.style.WARNING(
                                f"'{preferred_sheet}' 없음 → '{first_sn}' 사용: {rel}"
                            )
                        )

            parsed_files.append((path, ctx, sheets_data))

        if dry:
            for path, ctx, sheets_data in parsed_files:
                rel = path.relative_to(root)
                mode = "all-sheets" if all_sheets_mode else "단일 시트"
                self.stdout.write(
                    f"[dry] {rel} → {ctx.year} {ctx.venue} 부={ctx.session_part} "
                    f"지교회={ctx.branch_label!r} ({mode}) 시트={list(sheets_data.keys())}"
                )
                for sn, (_, tm) in sheets_data.items():
                    snap = sn[:200] if all_sheets_mode else ""
                    n = sum(len(v) for v in tm.values())
                    self.stdout.write(
                        f"        · {sn} snapshot={snap!r}: 팀 {len(tm)}개, 이름 {n}건"
                    )
            self.stdout.write(
                self.style.WARNING(
                    f"dry-run 완료 (스킵 {skipped}, 파싱 성공 {len(parsed_files)})"
                )
            )
            return

        with transaction.atomic():
            div, _ = Division.objects.get_or_create(
                code=division_code,
                defaults={"name": "청년부", "sort_order": 10},
            )

            used_ik: set[str] = set(
                Member.objects.exclude(import_key="").values_list(
                    "import_key", flat=True
                )
            )
            by_name: dict[str, Member] = {}
            for m in Member.objects.all():
                key = re.sub(r"\s+", "", (m.name or "").strip())
                if key:
                    by_name[key] = m

            created_members = 0
            mdt_created = 0
            scope_created = 0
            entry_created = 0
            entry_updated = 0
            entry_skipped_conflict = 0

            for path, ctx, sheets_data in parsed_files:
                rel_str = str(path.relative_to(root))
                for sheet_name, (team_cols, team_members) in sheets_data.items():
                    snapshot_label = sheet_name[:200] if all_sheets_mode else ""
                    scope, sc = WorshipRosterScope.objects.get_or_create(
                        division=div,
                        venue=ctx.venue,
                        year=ctx.year,
                        session_part=ctx.session_part,
                        branch_label=ctx.branch_label or "",
                        snapshot_label=snapshot_label,
                        defaults={"sort_order": 0},
                    )
                    if sc:
                        scope_created += 1

                    team_objs: dict[str, Team] = {}
                    for order, (_, raw_name) in enumerate(team_cols):
                        slug = TEAM_SLUG.get(raw_name)
                        if not slug:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"알 수 없는 팀 스킵: {raw_name} ({rel_str})"
                                )
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

                            mdt, mcreated = MemberDivisionTeam.objects.get_or_create(
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
                            if mcreated:
                                mdt_created += 1
                            else:
                                if mdt.team_id != team.id:
                                    mdt.team = team
                                    mdt.save(update_fields=["team"])
                                if not member.division_teams.filter(
                                    division=div, is_primary=True
                                ).exists():
                                    mdt.is_primary = True
                                    mdt.save(update_fields=["is_primary"])

                            try:
                                entry = WorshipRosterEntry.objects.get(
                                    scope=scope, member=member
                                )
                            except WorshipRosterEntry.DoesNotExist:
                                entry = WorshipRosterEntry(
                                    scope=scope,
                                    member=member,
                                    team=team,
                                    source_rel_path=rel_str,
                                    sheet_name=sheet_name,
                                )
                                try:
                                    entry.full_clean()
                                    entry.save()
                                except ValidationError as e:
                                    entry_skipped_conflict += 1
                                    msg = (
                                        f"명단 검증 실패(저장 안 함): {member.name} "
                                        f"scope={scope} {rel_str} — "
                                        f"{e.message_dict or e.messages}"
                                    )
                                    self.stdout.write(self.style.WARNING(msg))
                                    logger.warning(msg)
                                    continue
                                entry_created += 1
                            else:
                                changed = False
                                if entry.team_id != team.id:
                                    entry.team = team
                                    changed = True
                                if entry.source_rel_path != rel_str:
                                    entry.source_rel_path = rel_str
                                    changed = True
                                if entry.sheet_name != sheet_name:
                                    entry.sheet_name = sheet_name
                                    changed = True
                                if changed:
                                    try:
                                        entry.full_clean()
                                    except ValidationError as e:
                                        entry_skipped_conflict += 1
                                        msg = (
                                            f"명단 갱신 스킵(검증 실패): {member.name} "
                                            f"scope={scope} — {e.message_dict or e.messages}"
                                        )
                                        self.stdout.write(self.style.WARNING(msg))
                                        logger.warning(msg)
                                        continue
                                    entry.save()
                                    entry_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: 스킵 {skipped}, 구분 신규 {scope_created}, "
                f"Member 신규 {created_members}, 소속 신규 {mdt_created}, "
                f"명단행 신규 {entry_created}, 명단행 갱신 {entry_updated}, "
                f"명단 검증 스킵 {entry_skipped_conflict}"
            )
        )
