"""변경 이력 문장 변환 테스트."""

from __future__ import annotations

from django.test import TestCase, override_settings

from retreat.services.changelog_format import _diff_lines, _format_value


@override_settings(TIME_ZONE="Asia/Seoul", USE_TZ=True)
class ChangelogFormatDatetimeTests(TestCase):
    def test_format_value_formats_iso_datetime_without_seconds(self):
        self.assertEqual(
            _format_value(
                "checked_in_at",
                "2026-06-12T14:16:54.797865+00:00",
            ),
            "2026.06.12 23:16",
        )
        self.assertEqual(
            _format_value(
                "expected_check_in_at",
                "2026-06-18T14:15:00+00:00",
            ),
            "2026.06.18 23:15",
        )
        self.assertEqual(
            _format_value(
                "expected_check_in_at",
                "2026-06-18T23:15:00+09:00",
            ),
            "2026.06.18 23:15",
        )

    def test_diff_lines_use_human_readable_datetimes(self):
        lines = _diff_lines(
            {
                "check_in_status": "pending",
                "checked_in_at": "2026-06-12T14:16:54.797865+00:00",
            },
            {
                "check_in_status": "checked_in",
                "checked_in_at": "2026-06-18T14:15:29.363881+00:00",
            },
        )
        joined = "; ".join(lines)
        self.assertIn("입·퇴실: 입실전 → 입실", joined)
        self.assertIn("실제 입실 시각: 2026.06.12 23:16 → 2026.06.18 23:15", joined)
        self.assertNotIn("T14:16:54", joined)
