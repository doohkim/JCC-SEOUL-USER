"""
앱 전역 TextChoices 등. models 패키지와 같은 단위로 파일을 나눔.

- member_relationship: 멤버 가족 관계, 심방 연락 방식
- attendance: 예배 출석 명단 구분
"""

from .attendance import (
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
