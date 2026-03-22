"""
앱 전역 TextChoices 등.

출석 관련 상수는 ``attendance.choices``가 단일 출처입니다.
여기서는 하위 호환을 위해 re-export 합니다.
"""

from attendance.choices import (
    ATTENDANCE_CHIP_VALUES,
    AttendanceChip,
    MidweekAttendanceStatus,
    MidweekServiceType,
    WorshipVenue,
)
from .member_relationship import (
    RelationshipKind,
    ShepherdingContactMethod,
    VisitContactMethod,
)

__all__ = [
    "RelationshipKind",
    "ShepherdingContactMethod",
    "VisitContactMethod",
    "WorshipVenue",
    "MidweekServiceType",
    "MidweekAttendanceStatus",
    "AttendanceChip",
    "ATTENDANCE_CHIP_VALUES",
]
