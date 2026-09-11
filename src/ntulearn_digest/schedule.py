"""Weekly class times from NTU's public Class Schedule page (no login needed).

NTULearn does not expose lecture or tutorial times, so we read
https://wish.wis.ntu.edu.sg/webexe/owa/AUS_SCHEDULE.main_display1 and expand
each row into dated class meetings using the teaching-week calendar.
"""
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Sequence

from .util import COURSE_CODE

SCHEDULE_URL = "https://wish.wis.ntu.edu.sg/webexe/owa/AUS_SCHEDULE.main_display1"
DAYS = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


def fetch_schedule_html(code: str, acadsem: str, timeout: float = 40) -> str:
    data = urllib.parse.urlencode({
        "staff_access": "false", "acadsem": acadsem, "r_subj_code": code.upper(),
        "boption": "Search", "r_search_type": "F",
    }).encode()
    req = urllib.request.Request(SCHEDULE_URL, data=data, headers={"User-Agent": "ntulearn-digest"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("latin-1")


def _cells(row: str) -> List[str]:
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.I | re.S)
    return [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells]


def parse_schedule(page: str) -> List[dict]:
    """Rows: code, title, index, type, group, day, start, end, venue, remark."""
    rows: List[dict] = []
    code = title = ""
    index = ""
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.I | re.S):
        cells = _cells(row)
        if len(cells) == 3 and COURSE_CODE.fullmatch(cells[0]):
            code, title, index = cells[0], cells[1].rstrip("~* ").strip(), ""
            continue
        if len(cells) != 7 or not code:
            continue
        idx, typ, group, day, time, venue, remark = cells
        index = idx or index
        m = re.fullmatch(r"(\d{2})(\d{2})-(\d{2})(\d{2})", time.replace(" ", ""))
        if not m or day.upper() not in DAYS:
            continue
        rows.append({
            "code": code, "title": title, "index": index, "type": typ, "group": group,
            "day": day.upper(), "start": f"{m.group(1)}:{m.group(2)}", "end": f"{m.group(3)}:{m.group(4)}",
            "venue": venue, "remark": remark,
        })
    return rows


def parse_weeks(remark: Optional[str], default: Sequence[int] = tuple(range(1, 14))) -> List[int]:
    """'Teaching Wk2-13' -> [2..13]; 'Teaching Wk1,3,5' -> [1,3,5]; nothing -> weeks 1-13."""
    m = re.search(r"Wk\s*([\d,\-\s]+)", remark or "", flags=re.I)
    if not m:
        return list(default)
    weeks = set()
    for part in m.group(1).split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            if a.strip().isdigit() and b.strip().isdigit():
                weeks.update(range(int(a), int(b) + 1))
        elif part.isdigit():
            weeks.add(int(part))
    return sorted(w for w in weeks if 1 <= w <= 14) or list(default)


def teaching_week_monday(week1_monday: date, week: int, recess_after: int = 7) -> date:
    """NTU semesters have a recess week after teaching week 7."""
    return week1_monday + timedelta(weeks=week - 1 + (1 if week > recess_after else 0))


def select_rows(rows: Iterable[dict], code: str, index: Optional[str] = None, groups: Optional[Sequence[str]] = None) -> List[dict]:
    chosen = [r for r in rows if r["code"] == code.upper()]
    if index:
        chosen = [r for r in chosen if r["index"] == index]
    if groups:
        wanted = {g.upper() for g in groups}
        chosen = [r for r in chosen if r["group"].upper() in wanted]
    seen, unique = set(), []
    for r in chosen:
        key = (r["type"], r["group"], r["day"], r["start"], r["end"], r["venue"], r["remark"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def class_meetings(rows: Iterable[dict], week1_monday: date, recess_after: int = 7,
                   skip_dates: Iterable[date] = ()) -> List[dict]:
    """Expand schedule rows into dated items (naive local times, ISO strings)."""
    skip = set(skip_dates)
    items = []
    for r in rows:
        for w in parse_weeks(r.get("remark")):
            d = teaching_week_monday(week1_monday, w, recess_after) + timedelta(days=DAYS[r["day"]])
            if d in skip:
                continue
            start = datetime.combine(d, datetime.strptime(r["start"], "%H:%M").time())
            end = datetime.combine(d, datetime.strptime(r["end"], "%H:%M").time())
            label = r["type"].replace("LEC/STUDIO", "Lecture").replace("TUT", "Tutorial").replace("SEM", "Seminar")
            items.append({
                "uid": f"class-{r['code']}-{r['group']}-{r['type']}-{d.isoformat()}-{r['start']}".replace("/", "_").replace(" ", ""),
                "kind": "class", "course": r["code"], "title": f"{r['code']} {label} {r['group']}".strip(),
                "start": start.isoformat(), "end": end.isoformat(), "location": r["venue"],
                "detail": f"{r['title']} · Teaching week {w}", "source": "NTU Class Schedule",
            })
    return sorted(items, key=lambda x: x["start"])
