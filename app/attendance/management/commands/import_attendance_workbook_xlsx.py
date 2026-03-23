"""
한 파일 안의 여러 시트를 순회해 주일·수요·토요 출석을 일괄 반영.

**DB에 실제로 넣으려면 ``--dry-run`` 을 붙이지 마세요.** ``--dry-run`` 이면 파싱만 하고 저장하지 않습니다.
한 주일 시트만 넣은 경우( ``import_sunday_attendance_xlsx`` 단독 실행)에는 그 주차·그 시트만 반영됩니다.

제외: 시트명에 ``사본``, ``주일 88``, ``주일 인천``, ``집회``, ``전도명단``, ``예상명단`` 포함.
포함: ``주일예배``, ``수요예배``, ``토요예배`` 가 이름에 들어 있는 시트.

사용::

    python manage.py import_attendance_workbook_xlsx _test_rosters/2026/2026\\ 예배\\ 출석\\ 명단.xlsx
    python manage.py import_attendance_workbook_xlsx path/to/file.xlsx --dry-run   # DB 미반영
"""

from __future__ import annotations

from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from attendance.importers.workbook_sheet_filter import workbook_sheet_kind


class Command(BaseCommand):
    help = (
        "통합 엑셀의 주일·수요·토요 시트를 모두 DB에 반영 (--dry-run 없이 실행 시 저장). "
        "단일 시트만 반영하려면 import_sunday_attendance_xlsx / import_midweek_attendance_xlsx 를 쓰세요."
    )

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str, help="엑셀 파일 경로")
        parser.add_argument(
            "--division-code",
            default="youth",
            help="Division code (기본: youth)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="각 시트별 dry-run 만 수행",
        )
        parser.add_argument(
            "--create-missing-members",
            action="store_true",
            help="교적 자동 생성 (각 하위 명령에 전달)",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="한 시트라도 실패하면 전체를 비정상 종료",
        )

    def handle(self, *args, **options):
        path = Path(options["xlsx_path"]).expanduser().resolve()
        if not path.is_file():
            raise CommandError(f"파일이 없습니다: {path}")

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    "※ --dry-run: 모든 시트는 파싱만 하고 출석 행은 DB에 저장하지 않습니다."
                )
            )

        try:
            import openpyxl
        except ImportError as e:
            raise CommandError("openpyxl이 필요합니다.") from e

        wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
        names = list(wb.sheetnames)
        wb.close()

        common = {
            "verbosity": options.get("verbosity", 1),
            "division_code": options["division_code"],
            "dry_run": options["dry_run"],
            "create_missing_members": options["create_missing_members"],
        }

        done = skip = err = 0
        for sheet in names:
            kind = workbook_sheet_kind(sheet)
            if kind is None:
                self.stdout.write(f"건너뜀: {sheet!r}")
                skip += 1
                continue
            self.stdout.write(self.style.NOTICE(f"=== {sheet!r} ({kind}) ==="))
            try:
                if kind == "sunday":
                    call_command(
                        "import_sunday_attendance_xlsx",
                        str(path),
                        sheet=sheet,
                        **common,
                    )
                else:
                    call_command(
                        "import_midweek_attendance_xlsx",
                        str(path),
                        sheet=sheet,
                        service_type=kind,
                        **common,
                    )
                done += 1
            except CommandError as e:
                self.stdout.write(
                    self.style.ERROR(f"실패 {sheet!r}: {e}")
                )
                err += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"끝: 처리 {done}개, 건너뜀 {skip}개, 실패 {err}개"
            )
        )
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    "위 실행은 dry-run 이었습니다. 관리자 화면 숫자는 바뀌지 않습니다. "
                    "저장하려면 같은 명령에서 --dry-run 을 빼고 다시 실행하세요."
                )
            )
        if err and options["strict"]:
            raise CommandError(f"{err}개 시트 임포트 실패 (--strict)")
