import os


# 팀 출석부(TeamAttendanceSession) 자동 생성 시 롤링 윈도우 크기(일).
# "오늘(포함) ~ 오늘+(ROLLING_DAYS-1)" 범위에서 수/토/주일 예배일만 깐다.
#
# 예) 3이면: 오늘~오늘+2
# 예) 7이면: 오늘~오늘+6
TEAM_ATTENDANCE_SESSION_ROLLING_DAYS = int(
    os.environ.get("TEAM_ATTENDANCE_SESSION_ROLLING_DAYS", "3")
)

