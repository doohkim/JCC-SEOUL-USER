"""
주일예배 참석자 명단 시트 → ``SundayAttendanceLine`` 저장 (부서 + 주일 예배일).

시트 예: ``26.03.22 주일예배`` — 상단 ``YYYY.MM.DD 주일예배 참석자 명단`` 에서 날짜 추출,
``부서 회장단`` / 팀 헤더 + (이름|현장|인천) 3열 블록 파싱.

현장:
  - 숫자 1~4 → 해당 부. **인천 열에 체크**되면 인천 해당 부, 체크 없으면 서울 해당 부.
 - 숫자 **5** → **3부·4부 연참** 표시(임포트 시 3부/4부 출석행으로 분해, ``session_part=3``, ``session_part=4``).
  - ``온`` → 온라인, ``지`` → 지교회
  - 이름만 있고 현장이 비어 있으면 **DB에 행을 만들지 않음**(불참으로 간주).

사용::

    python manage.py import_sunday_attendance_xlsx /path/to/file.xlsx --sheet "26.03.22 주일예배"
    python manage.py import_sunday_attendance_xlsx ~/Downloads/2026\\ 예배\\ 출석\\ 명단.xlsx --sheet "26.03.22 주일예배" --dry-run
"""

from __future__ import annotations

from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from attendance.choices import WorshipVenue
from attendance.importers.member_resolve import (
    allocate_import_key,
    find_member,
    member_name_key,
    resolve_team,
)
from attendance.importers.sunday_attendance_xlsx import (
    ParsedSundayAttendanceRow,
    parse_sunday_attendance_sheet,
)
from attendance.models import SundayAttendanceLine
from registry.importers.youth_roster_xlsx import load_workbook_rows
from registry.models import Member
from users.models import Division


def _dedupe_same_member_rows(
    parsed: list[ParsedSundayAttendanceRow],
) -> tuple[list[ParsedSundayAttendanceRow], int]:
    """
    동일 인물 이름이 여러 번 나온 경우만 정리한다.

    - 완전 동일한 (venue, 부, 지교 라벨) 중복 행은 하나만 남긴다.
 - **서로 다른 부** 는 모두 유지한다.
    - 현장(1~4부) 줄이 있는데 같은 이름에 온라인·지교 줄도 있으면 현장만 남긴다.
    """
    from collections import defaultdict

    def _sig(r: ParsedSundayAttendanceRow) -> tuple:
        return (r.venue, r.session_part, r.branch_label or "")

    groups: dict[str, list[ParsedSundayAttendanceRow]] = defaultdict(list)
    for r in parsed:
        groups[member_name_key(r.display_name)].append(r)

    out: list[ParsedSundayAttendanceRow] = []
    dropped = 0
    for _key, rows in groups.items():
        if len(rows) == 1:
            out.append(rows[0])
            continue

        seen: set[tuple] = set()
        uniq: list[ParsedSundayAttendanceRow] = []
        for r in rows:
            s = _sig(r)
            if s in seen:
                dropped += 1
                continue
            seen.add(s)
            uniq.append(r)

        physical = [
            r
            for r in uniq
            if r.venue in (WorshipVenue.SEOUL, WorshipVenue.INCHEON)
            and r.session_part > 0
        ]
        remote = [
            r
            for r in uniq
            if r.venue in (WorshipVenue.ONLINE, WorshipVenue.BRANCH)
        ]
        if physical and remote:
            out.extend(physical)
            dropped += len(remote)
            continue
        out.extend(uniq)
    return out, dropped


class Command(BaseCommand):
    help = "주일예배 참석자 명단 엑셀 → 주간 출석(주일 행) 저장"

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str, help="엑셀 파일 경로")
        parser.add_argument(
            "--sheet",
            required=True,
            help='시트 이름 (예: "26.03.22 주일예배")',
        )
        parser.add_argument(
            "--division-code",
            default="youth",
            help="청년부 Division code (기본: youth)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB에 쓰지 않고 파싱·매칭 통계만 출력",
        )
        parser.add_argument(
            "--create-missing-members",
            action="store_true",
            help="교적에 없는 이름은 Member 를 새로 만든 뒤 출석 행 저장 (부서회장단 등)",
        )

    def handle(self, *args, **options):
        path = Path(options["xlsx_path"]).expanduser().resolve()
        sheet_name = options["sheet"]
        division_code = options["division_code"]
        dry = options["dry_run"]

        if not path.is_file():
            raise CommandError(f"파일이 없습니다: {path}")

        try:
            rows = load_workbook_rows(path, sheet_name)
        except ImportError as e:
            raise CommandError("openpyxl이 필요합니다. pip install openpyxl") from e
        except ValueError as e:
            raise CommandError(str(e)) from e

        try:
            title_date, parsed = parse_sunday_attendance_sheet(rows)
        except ValueError as e:
            raise CommandError(str(e)) from e

        if not parsed:
            raise CommandError("파싱된 출석 행이 없습니다. 시트 형식을 확인하세요.")

        parsed, deduped = _dedupe_same_member_rows(parsed)
        if deduped:
            self.stdout.write(
                self.style.WARNING(
                    f"동일 인물 중복 행 {deduped}건 제거(동일 부·구분만 병합)"
                )
            )

        if title_date is None:
            self.stdout.write(
                self.style.WARNING(
                    "제목에서 날짜를 못 찾았습니다. 시트의 주일 날짜를 확인하세요."
                )
            )
            raise CommandError("날짜(YYYY.MM.DD)가 필요합니다.")

        self.stdout.write(
            f"주일 예배일(시트): {title_date} · 행 수: {len(parsed)}"
        )

        if dry:
            by_v = {}
            for r in parsed:
                k = (r.venue, r.session_part, r.branch_label or "")
                by_v[k] = by_v.get(k, 0) + 1
            for k, n in sorted(by_v.items(), key=lambda x: str(x[0])):
                self.stdout.write(f"  {k}: {n}명")
            self.stdout.write(self.style.WARNING("dry-run: DB 미반영"))
            return

        created_members = 0
        with transaction.atomic():
            div, _ = Division.objects.get_or_create(
                code=division_code,
                defaults={"name": "청년부", "sort_order": 10},
            )

            created = updated = 0
            skipped_no_member = 0
            skipped_validation = 0
            create_missing = options["create_missing_members"]
            used_ik: set[str] = set(
                Member.objects.exclude(import_key="").values_list("import_key", flat=True)
            )

            for row in parsed:
                team = resolve_team(row.team_header, div)
                member = find_member(row.display_name, team)
                if member is None:
                    member = find_member(row.display_name, None)
                if member is None and create_missing:
                    ik = allocate_import_key(row.display_name, used_ik)
                    member = Member.objects.create(
                        name=(row.display_name or "")[:50],
                        import_key=ik,
                    )
                    created_members += 1
                    self.stdout.write(
                        self.style.NOTICE(
                            f"교적 자동 생성: {row.display_name!r} (import_key={ik})"
                        )
                    )
                if member is None:
                    skipped_no_member += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"멤버 없음(스킵): {row.display_name!r} ({row.team_header})"
                        )
                    )
                    continue

                try:
                    try:
                        obj = SundayAttendanceLine.objects.get(
                            division=div,
                            member=member,
                            venue=row.venue,
                            session_part=row.session_part,
                            branch_label=row.branch_label or "",
                            service_date=title_date,
                        )
                        was_created = False
                    except SundayAttendanceLine.DoesNotExist:
                        obj = SundayAttendanceLine(
                            division=div,
                            member=member,
                            venue=row.venue,
                            session_part=row.session_part,
                            branch_label=row.branch_label or "",
                            service_date=title_date,
                        )
                        was_created = True
                    obj.service_date = title_date
                    obj.team = team
                    # 엑셀 팀 헤더를 그대로 스냅샷으로 저장한다.
                    obj.team_name_snapshot = (row.team_header or "").strip()[:100]
                    obj.full_clean()
                    obj.save()
                except ValidationError as e:
                    skipped_validation += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"검증 실패: {member.name} — {e.messages or e.message_dict}"
                        )
                    )
                    continue

                if was_created:
                    created += 1
                else:
                    updated += 1

        msg = (
            f"완료: 신규 {created}, 갱신 {updated}, "
            f"멤버 미매칭 {skipped_no_member}, 검증 실패 {skipped_validation}"
        )
        if options.get("create_missing_members") and not options["dry_run"]:
            msg += f", 교적 자동생성 {created_members}"
        self.stdout.write(self.style.SUCCESS(msg))
