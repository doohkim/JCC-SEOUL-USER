"""출석 임포트·파서 검증."""

from datetime import date

from django.test import SimpleTestCase

from attendance.choices import MidweekAttendanceStatus, WorshipVenue
from attendance.importers.midweek_attendance_xlsx import (
    ParsedMidweekAttendanceRow,
    _midweek_team_columns,
    dedupe_midweek_by_member,
    parse_midweek_attendance_sheet,
    parse_midweek_service_date,
)
from attendance.services.week_rollup import sunday_week_index_in_month
from attendance.importers.sunday_attendance_xlsx import (
    ParsedSundayAttendanceRow,
    parse_sunday_attendance_sheet,
)
from attendance.management.commands.import_sunday_attendance_xlsx import (
    _dedupe_same_member_rows,
)


class SundayAttendanceXlsxParseTests(SimpleTestCase):
    def test_sunday_header_includes_president_group_as_team_block(self):
        from attendance.importers.sunday_attendance_xlsx import _team_starts_from_header_row

        header = ("부서 회장단", "", "", "현혜팀", "", "", "미영팀")
        starts = _team_starts_from_header_row(header)
        self.assertEqual(starts[0], (0, "부서회장단"))
        self.assertEqual(starts[1], (3, "현혜팀"))
        self.assertEqual(starts[2], (6, "미영팀"))

    def test_sunday_header_two_column_format_keeps_all_teams(self):
        from attendance.importers.sunday_attendance_xlsx import _team_starts_from_header_row

        header = (
            "",
            "부서 회장단",
            "",
            "현혜팀",
            "",
            "주영팀",
            "",
            "재영팀",
            "",
            "주남팀",
            "",
            "광진팀",
            "",
            "미영팀",
        )
        starts = _team_starts_from_header_row(header)
        labels = [name for _, name in starts]
        self.assertIn("현혜팀", labels)
        self.assertIn("주영팀", labels)
        self.assertIn("미영팀", labels)

    def test_five_is_split_into_three_and_four(self):
        rows = [
            (None, "2026.03.22 주일예배 참석자 명단"),
            tuple(),
            (None, "부서 회장단", None, None, "연주팀", None, None),
            tuple(),
            (None, "현장", 0, "인천", "현장", 0, "인천"),
            (None, None, None, None, "홍길동", 5.0, None),
        ]
        d, parsed = parse_sunday_attendance_sheet(rows)
        self.assertEqual(d, date(2026, 3, 22))
        self.assertEqual(len(parsed), 2)
        parts = sorted([p.session_part for p in parsed])
        self.assertEqual(parts, [3, 4])
        for p in parsed:
            self.assertEqual(p.display_name, "홍길동")
            self.assertEqual(p.team_header, "연주팀")
            self.assertEqual(p.venue, WorshipVenue.SEOUL)

    def test_five_with_incheon_v_marks_split_incheon(self):
        rows = [
            (None, "2026.03.22 주일예배 참석자 명단"),
            (None, "부서 회장단", None, None, "경업팀", None, None),
            (None, "현장", 0, "인천", "현장", 0, "인천"),
            (None, None, None, None, "김철수", 5.0, "v"),
        ]
        _, parsed = parse_sunday_attendance_sheet(rows)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(sorted([p.session_part for p in parsed]), [3, 4])
        for p in parsed:
            self.assertEqual(p.venue, WorshipVenue.INCHEON)

    def test_dedupe_keeps_distinct_parts_same_person(self):
        rows = [
            ParsedSundayAttendanceRow(
                "나은우",
                "주남팀",
                WorshipVenue.INCHEON,
                3,
                "",
            ),
            ParsedSundayAttendanceRow(
                "나은우",
                "주남팀",
                WorshipVenue.INCHEON,
                4,
                "",
            ),
        ]
        out, dropped = _dedupe_same_member_rows(rows)
        self.assertEqual(dropped, 0)
        self.assertEqual(len(out), 2)

    def test_dedupe_drops_remote_when_physical_exists(self):
        rows = [
            ParsedSundayAttendanceRow(
                "이영희",
                "주영팀",
                WorshipVenue.SEOUL,
                3,
                "",
            ),
            ParsedSundayAttendanceRow(
                "이영희",
                "주영팀",
                WorshipVenue.ONLINE,
                0,
                "",
            ),
        ]
        out, dropped = _dedupe_same_member_rows(rows)
        self.assertEqual(dropped, 1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].venue, WorshipVenue.SEOUL)


class SundayWeekIndexTests(SimpleTestCase):
    def test_march_15_2026_is_third_sunday_of_month(self):
        self.assertEqual(sunday_week_index_in_month(date(2026, 3, 15)), 3)


class MidweekAttendanceParseTests(SimpleTestCase):
    def test_service_date_from_wednesday_title_beats_sheet_tab(self):
        rows = [
            ("2026.03.18 수요예배 참석자 명단",),
            ("26.03.25 수요예배",),
        ]
        d = parse_midweek_service_date(rows, "26.03.25 수요예배")
        self.assertEqual(d, date(2026, 3, 18))

    def test_parse_absent_when_no_venue_mark_present_when_marked(self):
        rows = [
            ("2026.03.18 수요예배 참석자 명단",),
            (),
            ("", "부서 회장단", "", "미영팀", "", "주영팀"),
            ("", "현장", "인천", "현장", "인천", "현장", "인천"),
            ("", "이름만", "", "참석자", "v", ""),
        ]
        d, parsed = parse_midweek_attendance_sheet(
            rows, sheet_name="26.03.25 수요예배", lenient_empty_venue=False
        )
        self.assertEqual(d, date(2026, 3, 18))
        by_name = {p.display_name: p.status for p in parsed}
        self.assertEqual(by_name["이름만"], MidweekAttendanceStatus.ABSENT)
        self.assertEqual(by_name["참석자"], MidweekAttendanceStatus.PRESENT)

    def test_lenient_includes_unmarked_names(self):
        rows = [
            ("2026.03.18 수요예배 참석자 명단",),
            (),
            ("", "부서 회장단", "", "미영팀", "", "주영팀"),
            ("", "현장", "인천", "현장", "인천", "현장", "인천"),
            ("", "무표시", "", "참석자", "v", ""),
        ]
        _, parsed = parse_midweek_attendance_sheet(rows, lenient_empty_venue=True)
        self.assertEqual(len(parsed), 2)
        names = {p.display_name for p in parsed}
        self.assertEqual(names, {"무표시", "참석자"})

    def test_midweek_team_columns_uses_team_header_position_not_fixed_stride(self):
        """팀 사이에 빈 열이 더 있어도 마지막 팀의 이름 열 = 팀열인덱스 - 2."""
        header = (
            "",
            "부서 회장단",
            "",
            "a팀",
            "",
            "b팀",
            "",
            "c팀",
            "",
            "d팀",
            "",
            "e팀",
            "",
            None,
            None,
            "미영팀",
        )
        cols = _midweek_team_columns(header)
        self.assertEqual(cols[-1][1], "미영팀")
        self.assertEqual(cols[-1][0], 13)

    def test_midweek_team_columns_includes_president_group(self):
        header = ("", "", "부서 회장단", "", "현혜팀", "", "미영팀")
        cols = _midweek_team_columns(header)
        self.assertEqual(cols[0], (0, "부서회장단"))

    def test_dedupe_midweek_prefers_present_over_absent(self):
        rows = [
            ParsedMidweekAttendanceRow("홍길동", "A팀", MidweekAttendanceStatus.ABSENT),
            ParsedMidweekAttendanceRow("홍길동", "B팀", MidweekAttendanceStatus.PRESENT),
        ]
        out, dropped = dedupe_midweek_by_member(rows)
        self.assertEqual(dropped, 1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].status, MidweekAttendanceStatus.PRESENT)


class TeamAttendanceSessionWindowTests(SimpleTestCase):
    def test_apr2_2026_thursday_window_lists_sat_sun_wed(self):
        from attendance.services.team_attendance_sessions import (
            worship_service_dates_in_seven_day_window,
        )

        anchor = date(2026, 4, 2)
        self.assertEqual(anchor.weekday(), 3)
        got = worship_service_dates_in_seven_day_window(anchor)
        self.assertEqual(got, [date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 8)])

    def test_apr5_2026_sunday_window_includes_next_sunday(self):
        from attendance.services.team_attendance_sessions import (
            worship_service_dates_in_seven_day_window,
        )

        anchor = date(2026, 4, 5)
        self.assertEqual(anchor.weekday(), 6)
        got = worship_service_dates_in_seven_day_window(anchor)
        self.assertIn(date(2026, 4, 11), got)
