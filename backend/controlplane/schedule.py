"""저장소별 배치 스케줄 표현/검증 헬퍼."""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

TZ = ZoneInfo("Asia/Seoul")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_LABELS = {
    "mon": "월", "tue": "화", "wed": "수", "thu": "목",
    "fri": "금", "sat": "토", "sun": "일",
}
DEFAULT_CRON = "0 20 * * mon-fri"
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def build_cron(schedule_time: str, weekdays: list[str] | tuple[str, ...]) -> str:
    time = str(schedule_time or "").strip()
    if not _TIME_RE.match(time):
        raise ValueError("schedule_time은 HH:MM 형식이어야 합니다.")
    days = [str(d).lower().strip() for d in weekdays if str(d).strip()]
    invalid = [d for d in days if d not in WEEKDAYS]
    if invalid:
        raise ValueError(f"지원하지 않는 요일: {invalid}")
    if not days:
        raise ValueError("schedule_weekdays는 최소 1개 이상이어야 합니다.")
    hour, minute = time.split(":")
    day_expr = _compress_weekdays(days)
    cron = f"{int(minute)} {int(hour)} * * {day_expr}"
    validate_cron(cron)
    return cron


def validate_cron(cron: str) -> str:
    value = str(cron or "").strip()
    if not value:
        return ""
    try:
        CronTrigger.from_crontab(value, timezone=TZ)
    except ValueError as e:
        raise ValueError(f"잘못된 cron 표현식: {value}") from e
    return value


def normalize_schedule_payload(payload: dict, current_cron: str = "") -> str:
    if "schedule_time" in payload or "schedule_weekdays" in payload:
        weekdays = payload.get("schedule_weekdays")
        if isinstance(weekdays, str):
            weekdays = [d.strip() for d in weekdays.split(",") if d.strip()]
        if weekdays is None:
            parsed = parse_cron(str(payload.get("schedule_cron") or current_cron or DEFAULT_CRON))
            weekdays = parsed["weekdays"]
        return build_cron(str(payload.get("schedule_time") or parse_cron(current_cron or DEFAULT_CRON)["time"]), weekdays)
    if "schedule_cron" in payload:
        return validate_cron(str(payload.get("schedule_cron") or ""))
    return current_cron or ""


def parse_cron(cron: str) -> dict:
    value = str(cron or "").strip() or DEFAULT_CRON
    parts = value.split()
    time = "20:00"
    weekdays: list[str] = ["mon", "tue", "wed", "thu", "fri"]
    editable = False
    if len(parts) == 5:
        minute, hour, _, _, dow = parts
        if minute.isdigit() and hour.isdigit():
            time = f"{int(hour):02d}:{int(minute):02d}"
        parsed_days = _expand_weekdays(dow)
        if parsed_days:
            weekdays = parsed_days
            editable = True
    return {
        "cron": "" if not str(cron or "").strip() else value,
        "effective_cron": value,
        "time": time,
        "weekdays": weekdays,
        "label": describe_cron(value),
        "editable": editable,
    }


def describe_cron(cron: str) -> str:
    parsed = parse_cron_without_label(cron)
    day_label = "·".join(WEEKDAY_LABELS[d] for d in parsed["weekdays"]) if parsed["weekdays"] else parsed["day_expr"]
    return f"{day_label} {parsed['time']} KST"


def next_fire(cron: str) -> str:
    value = str(cron or "").strip() or DEFAULT_CRON
    trigger = CronTrigger.from_crontab(value, timezone=TZ)
    next_at = trigger.get_next_fire_time(None, datetime.now(TZ))
    return next_at.isoformat() if next_at else ""


def parse_cron_without_label(cron: str) -> dict:
    value = str(cron or "").strip() or DEFAULT_CRON
    parts = value.split()
    if len(parts) != 5:
        return {"time": "?", "weekdays": [], "day_expr": value}
    minute, hour, _, _, dow = parts
    time = f"{int(hour):02d}:{int(minute):02d}" if minute.isdigit() and hour.isdigit() else f"{hour}:{minute}"
    return {"time": time, "weekdays": _expand_weekdays(dow), "day_expr": dow}


def _compress_weekdays(days: list[str]) -> str:
    unique = [d for d in WEEKDAYS if d in set(days)]
    if unique == ["mon", "tue", "wed", "thu", "fri"]:
        return "mon-fri"
    if unique == list(WEEKDAYS):
        return "mon-sun"
    return ",".join(unique)


def _expand_weekdays(expr: str) -> list[str]:
    out: list[str] = []
    for part in str(expr or "").lower().split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, _, end = part.partition("-")
            if start in WEEKDAYS and end in WEEKDAYS:
                a, b = WEEKDAYS.index(start), WEEKDAYS.index(end)
                rng = WEEKDAYS[a:b + 1] if a <= b else WEEKDAYS[a:] + WEEKDAYS[:b + 1]
                out.extend(rng)
        elif part in WEEKDAYS:
            out.append(part)
    return [d for d in WEEKDAYS if d in set(out)]
