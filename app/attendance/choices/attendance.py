"""출석 명단(예배 구분) 관련 choices."""

from django.db import models


class WorshipVenue(models.TextChoices):
    INCHEON = "incheon", "인천 예배"
    SEOUL = "seoul", "서울 예배"
    ONLINE = "online", "온라인"
    BRANCH = "branch", "지교회"


class MidweekServiceType(models.TextChoices):
    WEDNESDAY = "wednesday", "수요일 예배"
    SATURDAY = "saturday", "토요일 예배"


class MidweekAttendanceStatus(models.TextChoices):
    PRESENT = "present", "참석"
    ABSENT = "absent", "불참"
    ONLINE = "online", "온라인"


class AttendanceChip(models.TextChoices):
    UNSET = "unset", "미선택"
    INCHEON = "incheon", "인천"
    SEOUL = "seoul", "서울"
    ONLINE = "online", "온라인"
    BRANCH = "branch", "지교회"


ATTENDANCE_CHIP_VALUES = frozenset(c.value for c in AttendanceChip)
