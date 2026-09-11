"""Small helpers shared by every module: file names, HTML to text, time zones."""
from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, Optional

_BAD = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
COURSE_CODE = re.compile(r"\b([A-Z]{2,3}\d{4}[A-Z]?)\b")


def safe_name(name: Optional[str], limit: int = 120) -> str:
    """Make a string safe as a file or folder name, keeping the extension when truncating."""
    s = _BAD.sub("_", (name or "file").strip()).strip(". ")
    if len(s) > limit:
        root, ext = os.path.splitext(s)
        if len(ext) > 12:
            ext = ""
        s = root[: limit - len(ext)].rstrip(". ") + ext
    return s or "file"


def html_to_text(s: Optional[str]) -> str:
    """Rough but dependable HTML to plain text for Blackboard bodies and announcements."""
    if not s:
        return ""
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", s, flags=re.I | re.S)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h[1-6]|ul|ol|table)>", "\n", s, flags=re.I)
    s = re.sub(r"<li[^>]*>", "- ", s, flags=re.I)
    s = re.sub(r"</t[dh]>", " | ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def get_tz(name: str) -> tzinfo:
    """ZoneInfo when available; NTU's Asia/Singapore falls back to a fixed +08:00 (no DST)."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        if name in ("Asia/Singapore", "Asia/Shanghai", "Asia/Hong_Kong", "Asia/Kuala_Lumpur"):
            return timezone(timedelta(hours=8), name)
        return timezone.utc


def parse_utc(value: Optional[str]) -> Optional[datetime]:
    """Blackboard timestamps look like 2026-09-13T15:59:00.000Z."""
    if not value:
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def from_iso(value: Optional[str], tz: Optional[tzinfo] = None) -> Optional[datetime]:
    """Parse ISO strings from snapshots or events.json. Naive values are taken as local time."""
    if not value:
        return None
    v = value.strip().replace("Z", "+00:00")
    if len(v) == 10:
        v += "T00:00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None and tz is not None:
        dt = dt.replace(tzinfo=tz)
    return dt


def course_code(*texts: Optional[str]) -> str:
    for t in texts:
        m = COURSE_CODE.search((t or "").upper())
        if m:
            return m.group(1)
    return ""


def course_slug(course: dict) -> str:
    """HE3001-MICROECONOMICS III AY26/27 Sem 1 Main -> HE3001-Microeconomics-III-Main"""
    name = course.get("name") or course.get("courseId") or course.get("id") or "course"
    code = course_code(name, course.get("courseId"))
    rest = name
    if code and rest.upper().startswith(code):
        rest = rest[len(code):]
    rest = re.sub(r"\bAY\s?\d{2}/\d{2}\b", " ", rest, flags=re.I)
    rest = re.sub(r"\bSem(ester)?\s?\d\b", " ", rest, flags=re.I)
    words = [w for w in re.split(r"[\s\-_~]+", rest) if w]
    pretty = []
    for w in words:
        pretty.append(w if (len(w) <= 3 and w.isupper()) or any(ch.isdigit() for ch in w) else w.capitalize())
    title = "-".join(pretty)
    return safe_name(f"{code}-{title}" if code else title, 90)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
