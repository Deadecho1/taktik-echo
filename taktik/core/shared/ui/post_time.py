"""Translate displayed post dates using the clock at capture, never at export."""

import re
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

MONTHS = {}
for month, names in enumerate(
    (
        "january jan janvier janv",
        "february feb février févr",
        "march mar mars",
        "april apr avril avr",
        "may mai",
        "june jun juin",
        "july jul juillet juil",
        "august aug août",
        "september sep sept septembre",
        "october oct octobre",
        "november nov novembre",
        "december dec décembre déc",
    ),
    1,
):
    MONTHS.update(dict.fromkeys(names.split(), month))


def post_time_utc(label, captured_at):
    """Return an ISO date, or a UTC timestamp when a time can be inferred."""
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("Capture time must include a timezone.")
    now = captured_at.astimezone(UTC)
    text = " ".join(label.casefold().split()).split(" • ")[0].strip()
    relative = re.fullmatch(
        r"(?:il y a )?(\d+)\s*(secondes?|seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|heures?|days?|d|jours?|j)(?: ago)?",
        text,
    )
    try:
        if relative:
            amount, unit = relative.groups()
            unit = unit[0]
            delta = {
                "s": "seconds",
                "m": "minutes",
                "h": "hours",
                "d": "days",
                "j": "days",
            }[unit]
            result = now - timedelta(**{delta: int(amount)})
            if delta == "days":
                return result.date().isoformat()
        else:
            result = _calendar_date(text, now)
            if result and not re.match(r"\d{4}-\d{2}-\d{2}t", text):
                return result.date().isoformat()
        return (
            result.isoformat(timespec="seconds").replace("+00:00", "Z")
            if result
            else None
        )
    except (ValueError, OverflowError):
        return None


def _calendar_date(text, now):
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=UTC)
    # ISO timestamps sometimes appear in captured metadata and carry a real time.
    if re.match(r"\d{4}-\d{2}-\d{2}t", text):
        result = datetime.fromisoformat(text.upper())
        return result.astimezone(UTC) if result.tzinfo else None
    words = text.replace(",", "").replace(".", "").split()
    if len(words) not in (2, 3):
        return None
    first, second = words[:2]
    if first in MONTHS:
        month, day = MONTHS[first], int(second)
    elif second in MONTHS:
        month, day = MONTHS[second], int(first)
    else:
        return None
    year = int(words[2]) if len(words) == 3 else now.year
    result = datetime(year, month, day, tzinfo=UTC)
    if len(words) == 2 and result.date() > now.date():
        result = result.replace(year=year - 1)
    return result


def tiktok_post_time_utc(label, captured_at):
    """TikTok's numeric calendar labels use month-day or year-month-day."""
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("Capture time must include a timezone.")
    text = label.strip(" \t\r\n·•|\u200e\u200f")
    match = re.fullmatch(r"(?:(\d{4})-)?(\d{1,2})-(\d{1,2})", text)
    if not match:
        return post_time_utc(text, captured_at)
    year, month, day = match.groups()
    now = captured_at.astimezone(UTC)
    years = [int(year)] if year else range(now.year, max(0, now.year - 9), -1)
    for candidate in years:
        try:
            result = datetime(candidate, int(month), int(day), tzinfo=UTC)
        except ValueError:
            continue
        if year or result.date() <= now.date():
            return result.date().isoformat()
    return None
