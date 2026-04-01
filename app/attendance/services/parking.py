"""주차권: 한국(Asia/Seoul) 달력·시각."""

from __future__ import annotations

from datetime import date

from zoneinfo import ZoneInfo

from django.utils import timezone

KST = ZoneInfo("Asia/Seoul")


def korea_today() -> date:
    """서버 설정과 무관하게 한국 시각 기준 오늘 날짜."""
    return timezone.now().astimezone(KST).date()


def parking_request_allowed_now(division_id: int | None) -> tuple[bool, str]:
    """
    한국 시각 기준 현재 시각이 해당 부서의 오늘 요일 신청 구간 안인지.
    반환: (가능 여부, 불가 시 안내 문구)
    """
    if not division_id:
        return False, "소속 부서 정보가 없어 주차권을 신청할 수 없습니다."

    from attendance.models import ParkingPermitWindow

    now = timezone.now().astimezone(KST)
    wd = now.weekday()
    t = now.time()
    qs = ParkingPermitWindow.objects.filter(
        division_id=division_id,
        weekday=wd,
        is_active=True,
    )
    if not qs.exists():
        return (
            False,
            "오늘은 이 부서에 설정된 주차권 신청 가능 시간이 없습니다. 아래 표를 참고하세요.",
        )
    for w in qs:
        if w.start_time <= t <= w.end_time:
            return True, ""
    return (
        False,
        "지금은 주차권을 신청할 수 있는 시간이 아닙니다. 아래 신청 가능 시간을 확인해 주세요.",
    )


def parking_windows_display(division_id: int | None) -> list[dict[str, str]]:
    """부서별 신청 가능 요일·시간 표시용."""
    if not division_id:
        return []

    from attendance.models import ParkingPermitWindow

    out: list[dict[str, str]] = []
    for w in ParkingPermitWindow.objects.filter(division_id=division_id, is_active=True).order_by(
        "weekday", "start_time"
    ):
        out.append(
            {
                "weekday_label": w.get_weekday_display(),
                "start": w.start_time.strftime("%H:%M"),
                "end": w.end_time.strftime("%H:%M"),
            }
        )
    return out
