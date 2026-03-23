"""출석 REST API 뷰 (``urls.py`` 에서 import)."""

from attendance.apis.divisions_meta import (
    AttendanceDivisionListView,
    AttendanceMetaChoicesView,
    AttendanceTeamListView,
)
from attendance.apis.records import (
    AttendanceMidweekRecordListView,
    AttendanceSundayLineListView,
)
from attendance.apis.weeks import AttendanceWeekListView, AttendanceWeekSummaryView
from attendance.apis.roster import (
    AttendanceMidweekRosterView,
    AttendanceSundayRosterView,
)
from attendance.apis.team_roster_check import (
    AttendanceTeamMidweekRosterView,
    AttendanceTeamSundayRosterView,
)

__all__ = [
    "AttendanceDivisionListView",
    "AttendanceMetaChoicesView",
    "AttendanceMidweekRecordListView",
    "AttendanceSundayLineListView",
    "AttendanceTeamListView",
    "AttendanceWeekListView",
    "AttendanceWeekSummaryView",
    "AttendanceMidweekRosterView",
    "AttendanceSundayRosterView",
    "AttendanceTeamSundayRosterView",
    "AttendanceTeamMidweekRosterView",
]
