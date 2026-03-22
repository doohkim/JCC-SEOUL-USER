"""
주일예배 참석자 명단 시트 → ``AttendanceWeek`` + ``SundayAttendanceLine`` 저장.

시트 예: ``26.03.22 주일예배`` — 상단 ``YYYY.MM.DD 주일예배 참석자 명단`` 에서 날짜 추출,
``부서 회장단`` / 팀 헤더 + (이름|현장|인천) 3열 블록 파싱.

현장:
  - 숫자 1~6 → 부. 인천 열에 V/v/✓ 이면 인천, 아니면 서울.
  - ``온`` → 온라인
  - ``지`` → 지교회

사용::

    python manage.py import_sunday_attendance_xlsx /path/to/file.xlsx --sheet "26.03.22 주일예배"
    python manage.py import_sunday_attendance_xlsx ~/Downloads/2026\\ 예배\\ 출석\\ 명단.xlsx --sheet "26.03.22 주일예배" --dry-run
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.choices.attendance import WorshipVenue
from users.importers.sunday_attendance_xlsx import (
    ParsedSundayAttendanceRow,
    parse_sunday_attendance_sheet,
)
from users.importers.youth_roster_xlsx import TEAM_SLUG, load_workbook_rows
from users.models import (
    AttendanceWeek,
    Division,
    Member,
    SundayAttendanceLine,
    Team,
)


def _week_sunday_on_or_before(d: date) -> date:
    from datetime import timedelta

    delta = (d.weekday() + 1) % 7
    return d - timedelta(days=delta)


def _member_name_key(name: str) -> str:
    s = re.sub(r"\s*(팀장|셀장|부장|회장)\s*$", "", (name or "").strip())
    return re.sub(r"\s+", "", s)


def _find_member(display_name: str, team: Team | None) -> Member | None:
    key = _member_name_key(display_name)
    if not key or len(key) < 2:
        return None
    qs = Member.objects.filter(is_active=True)
    if team is not None:
        in_team = qs.filter(
            division_teams__team_id=team.id,
            division_teams__division_id=team.division_id,
        ).distinct()
        for m in in_team:
            if _member_name_key(m.name) == key:
                return m
            if m.name_alias and _member_name_key(m.name_alias) == key:
                return m
    for m in qs:
        if _member_name_key(m.name) == key:
            return m
        if m.name_alias and _member_name_key(m.name_alias) == key:
            return m
    return None


def _dedupe_same_member_rows(
    parsed: list[ParsedSundayAttendanceRow],
) -> tuple[list[ParsedSundayAttendanceRow], int]:
    """
    엑셀에 동일 인물이 팀별로 중복 기재된 경우(예: 서울 3부 + 온라인).

    한 주에 한 줄만 남기고, **서울/인천 현장(부 번호)** 을 온라인·지교회보다 우선.
    """
    from collections import defaultdict

    groups: dict[str, list[ParsedSundayAttendanceRow]] = defaultdict(list)
    for r in parsed:
        groups[_member_name_key(r.display_name)].append(r)

    out: list[ParsedSundayAttendanceRow] = []
    dropped = 0
    for _key, rows in groups.items():
        if len(rows) == 1:
            out.append(rows[0])
            continue
        physical = [
            r
            for r in rows
            if r.venue in (WorshipVenue.SEOUL, WorshipVenue.INCHEON)
            and r.session_part > 0
        ]
        if physical:
            out.append(physical[0])
            dropped += len(rows) - 1
            continue
        out.append(rows[0])
        dropped += len(rows) - 1
    return out, dropped


def _resolve_team(team_header: str, division: Division) -> Team | None:
    t = team_header.replace(" ", "").strip()
    if "회장단" in t and "팀" not in t:
        return None
    slug = TEAM_SLUG.get(t)
    if not slug:
        return None
    return Team.objects.filter(division=division, code=slug).first()


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
                    f"동일 인물 중복 행 {deduped}건 제거(현장 부 우선, 나머지 무시)"
                )
            )

        if title_date is None:
            self.stdout.write(
                self.style.WARNING(
                    "제목에서 날짜를 못 찾았습니다. 시트의 주일 날짜를 확인하세요."
                )
            )
            raise CommandError("날짜(YYYY.MM.DD)가 필요합니다.")

        week_sunday = _week_sunday_on_or_before(title_date)
        if week_sunday != title_date:
            self.stdout.write(
                self.style.WARNING(
                    f"기준 주일을 {title_date} → {week_sunday} 로 맞춤 (주차 키)"
                )
            )

        self.stdout.write(
            f"서비스일(시트): {title_date} · 기준 주일: {week_sunday} · 행 수: {len(parsed)}"
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

        with transaction.atomic():
            div, _ = Division.objects.get_or_create(
                code=division_code,
                defaults={"name": "청년부", "sort_order": 10},
            )
            week, _ = AttendanceWeek.objects.get_or_create(
                division=div,
                week_sunday=week_sunday,
                defaults={"note": "", "auto_created": False},
            )

            created = updated = 0
            skipped_no_member = 0
            skipped_validation = 0

            for row in parsed:
                team = _resolve_team(row.team_header, div)
                member = _find_member(row.display_name, team)
                if member is None:
                    member = _find_member(row.display_name, None)
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
                            week=week,
                            member=member,
                            venue=row.venue,
                            session_part=row.session_part,
                            branch_label=row.branch_label or "",
                        )
                        was_created = False
                    except SundayAttendanceLine.DoesNotExist:
                        obj = SundayAttendanceLine(
                            week=week,
                            member=member,
                            venue=row.venue,
                            session_part=row.session_part,
                            branch_label=row.branch_label or "",
                        )
                        was_created = True
                    obj.team = team
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

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: 신규 {created}, 갱신 {updated}, "
                f"멤버 미매칭 {skipped_no_member}, 검증 실패 {skipped_validation}"
            )
        )
