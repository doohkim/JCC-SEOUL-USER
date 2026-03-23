"""출석 주간 집계(차트·요약) 비즈니스 로직."""

from __future__ import annotations

from collections import defaultdict
import re

from django.db.models import Count

from attendance.choices import MidweekAttendanceStatus, MidweekServiceType, WorshipVenue
from attendance.services.week_rollup import midweek_records_for_week, sunday_lines_for_week


def _venue_label(code: str) -> str:
    return dict(WorshipVenue.choices).get(code, code)


def _midweek_status_label(code: str) -> str:
    return dict(MidweekAttendanceStatus.choices).get(code, code or "(미입력)")


def _normalize_team_label(name: str) -> str:
    label = (name or "").strip()
    compact = re.sub(r"\s+", "", label)
    if compact in {"부서회장단", "팀회장단"}:
        return "회장단"
    return label


def build_week_summary_payload(division, week_sunday: date, wtype: str) -> dict:
    wtype = (wtype or "all").lower()
    out: dict = {
        "week": {
            "division_code": division.code,
            "division_name": division.name,
            "week_sunday": week_sunday.isoformat(),
        },
        "worship_type": wtype,
        "sunday": None,
        "midweek": None,
    }

    if wtype in ("all", "sunday"):
        sun_qs = sunday_lines_for_week(division, week_sunday)
        by_venue = dict(
            sun_qs.values("venue").annotate(c=Count("id")).values_list("venue", "c")
        )
        by_venue_display = {_venue_label(k): v for k, v in by_venue.items()}
        by_part_rows = (
            sun_qs.filter(venue__in=[WorshipVenue.SEOUL, WorshipVenue.INCHEON])
            .values("venue", "session_part")
            .annotate(c=Count("id"))
        )
        by_part: list[dict] = []
        for r in by_part_rows:
            venue = r["venue"]
            venue_label = _venue_label(venue)
            part = r["session_part"]
            c = r["c"]

            # legacy: session_part=5(3·4부 연참)을 연참 없이 3부/4부로 분해 표시
            if part == 5:
                by_part.append(
                    {
                        "venue": venue,
                        "venue_label": venue_label,
                        "session_part": 3,
                        "label": f"{venue_label} 3부",
                        "count": c,
                    }
                )
                by_part.append(
                    {
                        "venue": venue,
                        "venue_label": venue_label,
                        "session_part": 4,
                        "label": f"{venue_label} 4부",
                        "count": c,
                    }
                )
                continue

            by_part.append(
                {
                    "venue": venue,
                    "venue_label": venue_label,
                    "session_part": part,
                    "label": (
                        f"{venue_label} {part}부" if part else venue_label
                    ),
                    "count": c,
                }
            )
        team_rows = sun_qs.values("team_id", "team__name", "team_name_snapshot")
        team_buckets: dict[tuple[str, str | int], dict] = {}
        team_counts: defaultdict[tuple[str, str | int], int] = defaultdict(int)
        for row in team_rows:
            team_id = row.get("team_id")
            team_name = (row.get("team__name") or "").strip()
            snapshot = _normalize_team_label(row.get("team_name_snapshot") or "")
            if team_id:
                bucket_key = ("team", team_id)
                team_name_norm = _normalize_team_label(team_name)
                label = team_name_norm or snapshot or "팀 미지정"
            else:
                label = snapshot or "팀 미지정"
                bucket_key = ("name", label)
            if bucket_key not in team_buckets:
                team_buckets[bucket_key] = {
                    "team_id": team_id if team_id else None,
                    "team_name": label,
                }
            team_counts[bucket_key] += 1
        by_team = sorted(
            [
                {
                    "team_id": team_buckets[k]["team_id"],
                    "team_name": team_buckets[k]["team_name"],
                    "count": c,
                }
                for k, c in team_counts.items()
            ],
            key=lambda x: (-x["count"], x["team_name"]),
        )
        out["sunday"] = {
            "total_lines": sun_qs.count(),
            "by_venue": by_venue,
            "by_venue_display": by_venue_display,
            "by_venue_part": by_part,
            "by_team": by_team,
        }

    if wtype in ("all", "midweek", "wednesday", "saturday"):
        mw = midweek_records_for_week(division, week_sunday)
        if wtype == "wednesday":
            mw = mw.filter(service_type=MidweekServiceType.WEDNESDAY)
        elif wtype == "saturday":
            mw = mw.filter(service_type=MidweekServiceType.SATURDAY)

        by_service = {}
        for st, st_label in MidweekServiceType.choices:
            if wtype in ("wednesday", "saturday") and st != wtype:
                continue
            sub = mw.filter(service_type=st)
            agg = dict(
                sub.exclude(status__isnull=True)
                .values("status")
                .annotate(c=Count("id"))
                .values_list("status", "c")
            )
            by_status_labeled = {
                _midweek_status_label(k): v for k, v in agg.items()
            }
            null_c = sub.filter(status__isnull=True).count()
            if null_c:
                by_status_labeled["미입력"] = by_status_labeled.get("미입력", 0) + null_c
            by_service[st] = {
                "label": st_label,
                "total": sub.count(),
                "by_status": by_status_labeled,
            }
        out["midweek"] = {
            "total_records": mw.count(),
            "by_service": by_service,
        }

    return out


def build_meta_choices_payload() -> dict:
    return {
        "worship_types": [
            {"value": "all", "label": "전체"},
            {"value": "sunday", "label": "주일"},
            {"value": "wednesday", "label": "수요일"},
            {"value": "saturday", "label": "토요일"},
            {"value": "midweek", "label": "수·토 전체"},
        ],
        "venues": [{"value": c[0], "label": c[1]} for c in WorshipVenue.choices],
        "midweek_service_types": [
            {"value": c[0], "label": c[1]} for c in MidweekServiceType.choices
        ],
        "midweek_statuses": [
            {"value": c[0], "label": c[1]} for c in MidweekAttendanceStatus.choices
        ],
    }
