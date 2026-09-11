"""Write every output file from a snapshot: calendar, dashboard, Markdown and items.json."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .calendar_ics import build_calendar
from .dashboard import render_dashboard
from .report import collect_items, render_changes_md, render_course_md, render_deadlines_md
from .util import read_json, write_json, write_text


def load_events(path: Path) -> List[dict]:
    data = read_json(path, default=[])
    if isinstance(data, dict):
        data = data.get("events", [])
    return [x for x in data if isinstance(x, dict)]


def build_outputs(out: Path, snapshot: dict, diff: Optional[dict], events: List[dict], classes: List[dict],
                  tz_name: str = "Asia/Singapore", now: Optional[datetime] = None) -> Dict[str, Path]:
    items = collect_items(snapshot, events, classes, tz_name)
    term = snapshot.get("term") or "NTULearn"
    written = {
        "calendar": out / "calendar.ics",
        "calendar_no_classes": out / "calendar-deadlines-exams.ics",
        "dashboard": out / "dashboard.html",
        "deadlines": out / "deadlines.md",
        "changes": out / "changes.md",
        "items": out / "items.json",
    }
    write_text(written["calendar"], build_calendar(items, f"{term} 课表、考试与截止", tz_name, now=now))
    write_text(written["calendar_no_classes"],
               build_calendar([i for i in items if i["kind"] != "class"], f"{term} 考试与截止", tz_name, now=now))
    write_text(written["dashboard"], render_dashboard(snapshot, items, diff, tz_name, now=now))
    write_text(written["deadlines"], render_deadlines_md(items, snapshot, tz_name, now=now))
    write_text(written["changes"], render_changes_md(diff or {"first_run": True}, snapshot, tz_name))
    write_json(written["items"], items)
    for c in snapshot.get("courses", []):
        write_text(out / "courses" / c["slug"] / "overview.md", render_course_md(c, tz_name))
    return written
