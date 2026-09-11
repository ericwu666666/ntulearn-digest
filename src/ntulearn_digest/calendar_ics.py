"""RFC 5545 calendar output that imports cleanly into Apple, Google and Outlook calendars."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

from .util import from_iso, get_tz

ALARMS = {
    "deadline": ["-P1D", "-PT3H"],
    "exam": ["-P3D", "-PT2H"],
    "event": ["-P1D"],
    "class": [],
}


def escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\n").replace("\n", "\\n")


def fold(line: str) -> str:
    """Fold at 75 octets without splitting a multi-byte character."""
    if len(line.encode("utf-8")) <= 75:
        return line
    parts, cur, size, limit = [], [], 0, 75
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > limit:
            parts.append("".join(cur))
            cur, size, limit = [ch], n, 74
        else:
            cur.append(ch)
            size += n
    parts.append("".join(cur))
    return "\r\n ".join(parts)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_calendar(items: Iterable[dict], name: str, tz_name: str = "Asia/Singapore",
                   alarms: bool = True, now: Optional[datetime] = None) -> str:
    tz = get_tz(tz_name)
    stamp = _utc(now or datetime.now(timezone.utc))
    lines: List[str] = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ntulearn-digest//EN", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", f"X-WR-CALNAME:{escape(name)}", f"X-WR-TIMEZONE:{tz_name}",
    ]
    for it in items:
        start = from_iso(it.get("start"), tz)
        if start is None:
            continue
        kind = it.get("kind") or "event"
        end = from_iso(it.get("end"), tz)
        lines += ["BEGIN:VEVENT", f"UID:{it['uid']}@ntulearn-digest", f"DTSTAMP:{stamp}"]
        if it.get("all_day"):
            lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
            last = (end or start) + timedelta(days=1)
            lines.append(f"DTEND;VALUE=DATE:{last.strftime('%Y%m%d')}")
        elif kind == "deadline":
            lines.append(f"DTSTART:{_utc(start - timedelta(minutes=30))}")
            lines.append(f"DTEND:{_utc(start)}")
        else:
            lines.append(f"DTSTART:{_utc(start)}")
            lines.append(f"DTEND:{_utc(end or start + timedelta(hours=1))}")
        prefix = {"deadline": "截止 · ", "exam": "考试 · "}.get(kind, "")
        lines.append(f"SUMMARY:{escape(prefix + it.get('title', ''))}")
        detail = it.get("detail") or ""
        if it.get("source"):
            detail = (detail + "\n\n" if detail else "") + "来源：" + it["source"]
        if detail:
            lines.append(f"DESCRIPTION:{escape(detail)}")
        if it.get("location"):
            lines.append(f"LOCATION:{escape(it['location'])}")
        if it.get("url"):
            lines.append(f"URL:{it['url']}")
        lines.append(f"CATEGORIES:{kind.upper()}")
        if kind in ("deadline", "class"):
            lines.append("TRANSP:TRANSPARENT")
        if alarms and not it.get("done"):
            for trigger in ALARMS.get(kind, []):
                lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"TRIGGER:{trigger}",
                          f"DESCRIPTION:{escape(it.get('title', ''))}", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(x) for x in lines) + "\r\n"
