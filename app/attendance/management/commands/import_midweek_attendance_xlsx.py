"""
수요·토요 참석자 명단 엑셀 → ``MidweekAttendanceRecord`` (부서 + 예배일).

이름 옆 **현장** 열의 체크(v 등)·온라인 표시만 출석으로 본다. 표시가 없으면 **불참(absent)**.
``--lenient-venue`` 를 주면 빈 현장도 참석(구 스펙).
"""

from __future__ import annotations

from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from attendance.choices import MidweekAttendanceStatus, MidweekServiceType
from attendance.importers.member_resolve import (
    allocate_import_key,
    find_member,
    resolve_team,
)
from attendance.importers.midweek_attendance_xlsx import (
    ParsedMidweekAttendanceRow,
    dedupe_midweek_by_member,
    parse_midweek_attendance_sheet,
)
from attendance.models import MidweekAttendanceRecord
from registry.importers.youth_roster_xlsx import load_workbook_rows
from registry.models import Member
from users.models import Division


def _infer_service_type(sheet_name: str) -> str | None:
    s = sheet_name.replace(" ", "")
    if "수요예배" in s:
        return MidweekServiceType.WEDNESDAY
    if "토요예배" in s:
        return MidweekServiceType.SATURDAY
    return None


class Command(BaseCommand):
    help = "수요·토요예배 참석자 명단 엑셀 → 주간 출석(수·토 행) 저장"

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str, help="엑셀 파일 경로")
        parser.add_argument(
            "--sheet",
            required=True,
            help='시트 이름 (예: "26.03.25 수요예배")',
        )
        parser.add_argument(
            "--service-type",
            choices=["wednesday", "saturday"],
            default=None,
            help="미지정 시 시트 이름에서 수요/토요를 추론",
        )
        parser.add_argument(
            "--division-code",
            default="youth",
            help="청년부 Division code (기본: youth)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB에 쓰지 않고 파싱·통계만 출력",
        )
        parser.add_argument(
            "--create-missing-members",
            action="store_true",
            help="교적에 없는 이름은 Member 생성 후 저장",
        )
        parser.add_argument(
            "--lenient-venue",
            action="store_true",
            help="현장 열이 비어 있어도 이름만 있으면 참석으로 저장 (구 엑셀·구 스펙)",
        )

    def handle(self, *args, **options):
        path = Path(options["xlsx_path"]).expanduser().resolve()
        sheet_name = options["sheet"]
        division_code = options["division_code"]
        dry = options["dry_run"]

        st = options["service_type"] or _infer_service_type(sheet_name)
        if not st:
            raise CommandError(
                "예배 구분을 알 수 없습니다. --service-type wednesday|saturday 를 지정하세요."
            )

        if not path.is_file():
            raise CommandError(f"파일이 없습니다: {path}")

        try:
            rows = load_workbook_rows(path, sheet_name)
        except ImportError as e:
            raise CommandError("openpyxl이 필요합니다.") from e
        except ValueError as e:
            raise CommandError(str(e)) from e

        try:
            title_date, parsed = parse_midweek_attendance_sheet(
                rows,
                sheet_name=sheet_name,
                lenient_empty_venue=options["lenient_venue"],
            )
        except ValueError as e:
            raise CommandError(str(e)) from e

        if not parsed:
            raise CommandError("파싱된 이름이 없습니다. 시트 형식을 확인하세요.")

        parsed, deduped = dedupe_midweek_by_member(parsed)
        if deduped:
            self.stdout.write(
                self.style.WARNING(f"동일 인물 중복 열 {deduped}건 제거(이름 기준 1건)")
            )

        if title_date is None:
            raise CommandError("날짜(제목 YYYY.MM.DD 또는 시트명 YY.MM.DD)가 필요합니다.")

        self.stdout.write(
            f"예배일: {title_date} · 서비스: {st} · 인원(유니크): {len(parsed)}"
        )

        if dry:
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
                    obj, was_created = MidweekAttendanceRecord.objects.get_or_create(
                        division=div,
                        member=member,
                        service_type=st,
                        service_date=title_date,
                        defaults={
                            "status": row.status,
                        },
                    )
                    obj.service_date = title_date
                    obj.status = row.status
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
        if create_missing:
            msg += f", 교적 자동생성 {created_members}"
        self.stdout.write(self.style.SUCCESS(msg))
