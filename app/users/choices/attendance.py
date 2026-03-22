"""출석 명단(예배 구분) 관련 choices."""

from django.db import models


class WorshipVenue(models.TextChoices):
    """예배/출석이 속한 물리·형태 구분."""

    INCHEON = "incheon", "인천 예배"
    SEOUL = "seoul", "서울 예배"
    ONLINE = "online", "온라인"
    BRANCH = "branch", "지교회"


class MidweekServiceType(models.TextChoices):
    """주간 출석부 — 평일(수·토) 예배 구분."""

    WEDNESDAY = "wednesday", "수요일 예배"
    SATURDAY = "saturday", "토요일 예배"


class MidweekAttendanceStatus(models.TextChoices):
    """수·토 예배 출석 상태 (참석 / 불참 / 온라인)."""

    PRESENT = "present", "참석"
    ABSENT = "absent", "불참"
    ONLINE = "online", "온라인"


class AttendanceChip(models.TextChoices):
    """
    주일·이름 지정 출석 등 교시별 칩 선택 (앱 UI와 동일한 값).

    ``WorshipVenue`` 와 겹치는 코드(incheon, seoul, online, branch)는
    JSON ``picks`` 리스트에 그대로 저장합니다. ``unset`` = 미선택(입력됨).
    """

    UNSET = "unset", "미선택"
    INCHEON = "incheon", "인천"
    SEOUL = "seoul", "서울"
    ONLINE = "online", "온라인"
    BRANCH = "branch", "지교회"


ATTENDANCE_CHIP_VALUES = frozenset(c.value for c in AttendanceChip)
