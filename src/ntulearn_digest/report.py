"""Turn a snapshot (+ optional AI/manual events and class times) into items, diffs and Markdown."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

from .util import from_iso, get_tz, parse_utc

WEEKDAYS = "一二三四五六日"
EXAM_WORDS = re.compile(r"\b(mid[\s-]?term|final|exam|examination|test)\b", re.I)
STATUS_TEXT = {"todo": "成绩簿未见提交", "submitted": "已提交，待批改", "graded": "已评分"}


def fmt(dt: Optional[datetime], with_time: bool = True) -> str:
    if dt is None:
        return "—"
    s = f"{dt.month}/{dt.day} 周{WEEKDAYS[dt.weekday()]}"
    return f"{s} {dt:%H:%M}" if with_time else s


def column_status(col: dict) -> str:
    st = col.get("status")
    if st == "Graded" or (col.get("score") is not None and st is None):
        return "graded"
    if st:
        return "submitted"
    return "todo"


def _num(x) -> str:
    if x is None:
        return ""
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def collect_items(snapshot: dict, events: Iterable[dict] = (), classes: Iterable[dict] = (),
                  tz_name: str = "Asia/Singapore") -> List[dict]:
    tz = get_tz(tz_name)
    items: List[dict] = []
    for c in snapshot.get("courses", []):
        code = c.get("code") or c.get("name")
        for col in c.get("columns", []):
            due = parse_utc(col.get("due"))
            if due is None:
                continue
            st = column_status(col)
            score = f"{_num(col.get('score'))}/{_num(col.get('possible'))}" if col.get("score") is not None else ""
            items.append({
                "uid": f"col-{c['id']}-{col['id']}", "kind": "deadline", "course": code,
                "title": f"{code} {col.get('name')}", "name": col.get("name"),
                "start": due.astimezone(tz).isoformat(), "status": st, "done": st != "todo",
                "score": col.get("score"), "possible": col.get("possible"), "url": c.get("url"),
                "detail": "；".join(x for x in [f"满分 {_num(col.get('possible'))}" if col.get("possible") else "",
                                               STATUS_TEXT[st] + (f" {score}" if score else "")] if x),
                "source": "NTULearn 成绩簿",
            })
    for e in events:
        if not e.get("start") or not e.get("title"):
            continue
        start = from_iso(e["start"], tz)
        end = from_iso(e.get("end"), tz)
        course = e.get("course", "")
        kind = e.get("kind") or ("exam" if EXAM_WORDS.search(e["title"]) else "event")
        uid = e.get("uid") or "evt-" + hashlib.sha1(f"{course}|{e['title']}|{e['start']}".encode()).hexdigest()[:12]
        items.append({
            "uid": uid, "kind": kind, "course": course,
            "title": f"{course} {e['title']}".strip(), "name": e["title"],
            "start": start.isoformat(), "end": end.isoformat() if end else None,
            "all_day": len(e["start"].strip()) == 10, "location": e.get("location", ""),
            "weight": e.get("weight", ""), "detail": e.get("detail", ""),
            "source": e.get("source", "events.json"), "done": bool(e.get("done")),
        })
    for cl in classes:
        start = from_iso(cl["start"], tz)
        end = from_iso(cl.get("end"), tz)
        items.append({**cl, "start": start.isoformat(), "end": end.isoformat() if end else None})
    items.sort(key=lambda x: x["start"])
    return items


def diff_snapshots(old: Optional[dict], new: dict) -> dict:
    if not old:
        return {"first_run": True, "courses": [], "added_courses": [], "dropped_courses": []}
    old_courses = {c["id"]: c for c in old.get("courses", [])}
    new_ids = {c["id"] for c in new.get("courses", [])}
    out = {"first_run": False, "courses": [],
           "added_courses": [c["name"] for c in new.get("courses", []) if c["id"] not in old_courses],
           "dropped_courses": [c["name"] for cid, c in old_courses.items() if cid not in new_ids]}
    for c in new.get("courses", []):
        o = old_courses.get(c["id"])
        if not o:
            continue
        old_outline = {x["id"] for x in o.get("outline", [])}
        old_cols = {x["id"]: x for x in o.get("columns", [])}
        old_ann = {x["id"] for x in o.get("announcements", [])}
        entry = {
            "code": c.get("code"), "name": c.get("name"), "slug": c.get("slug"),
            "new_files": [f["path"] for f in c.get("files", []) if f.get("new")],
            "failed_files": [f"{f['path']} ({f['error']})" for f in c.get("files", []) if f.get("error")],
            "new_content": [x["path"] for x in c.get("outline", []) if x["id"] not in old_outline],
            "new_columns": [], "due_changed": [], "grade_changed": [],
            "new_announcements": [a for a in c.get("announcements", []) if a["id"] not in old_ann],
        }
        for col in c.get("columns", []):
            prev = old_cols.get(col["id"])
            if prev is None:
                entry["new_columns"].append(col)
                continue
            if prev.get("due") != col.get("due"):
                entry["due_changed"].append({"name": col["name"], "old": prev.get("due"), "new": col.get("due")})
            if (prev.get("status"), prev.get("score")) != (col.get("status"), col.get("score")):
                entry["grade_changed"].append({"name": col["name"], "status": col.get("status"), "score": col.get("score"),
                                               "possible": col.get("possible")})
        if any(entry[k] for k in ("new_files", "failed_files", "new_content", "new_columns",
                                  "due_changed", "grade_changed", "new_announcements")):
            out["courses"].append(entry)
    return out


def render_changes_md(diff: dict, snapshot: dict, tz_name: str) -> str:
    tz = get_tz(tz_name)
    when = from_iso(snapshot.get("generated_at"))
    lines = [f"# 本次同步的变化", "", f"同步时间：{fmt(when.astimezone(tz)) if when else '—'}", ""]
    if diff.get("first_run"):
        return "\n".join(lines + ["第一次同步，还没有可以比较的上一版。", ""])
    for label, key in (("新增课程", "added_courses"), ("不再出现的课程（可能已退选）", "dropped_courses")):
        if diff.get(key):
            lines += [f"## {label}", ""] + [f"- {n}" for n in diff[key]] + [""]
    if not diff["courses"] and not diff["added_courses"] and not diff["dropped_courses"]:
        lines.append("和上一次同步相比没有变化。")
    for c in diff["courses"]:
        lines += [f"## {c['code'] or c['name']}", ""]
        for col in c["new_columns"]:
            due = parse_utc(col.get("due"))
            lines.append(f"- 🆕 成绩项：{col['name']}，截止 {fmt(due.astimezone(tz)) if due else '无'}，满分 {_num(col.get('possible')) or '—'}")
        for d in c["due_changed"]:
            o, n = parse_utc(d["old"]), parse_utc(d["new"])
            lines.append(f"- ⏰ 截止时间变了：{d['name']}，{fmt(o.astimezone(tz)) if o else '无'} 改为 {fmt(n.astimezone(tz)) if n else '无'}")
        for g in c["grade_changed"]:
            st = column_status(g)
            score = f" {_num(g.get('score'))}/{_num(g.get('possible'))}" if g.get("score") is not None else ""
            lines.append(f"- ✅ {g['name']}：{STATUS_TEXT[st]}{score}")
        for a in c["new_announcements"]:
            created = parse_utc(a.get("created"))
            lines.append(f"- 📢 公告：{a['title']}（{fmt(created.astimezone(tz)) if created else ''}）")
        for p in c["new_content"][:30]:
            lines.append(f"- 📄 新内容：{p}")
        for p in c["new_files"]:
            lines.append(f"- 📥 新文件：`{p}`")
        for p in c["failed_files"]:
            lines.append(f"- ⚠️ 下载失败：`{p}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_deadlines_md(items: List[dict], snapshot: dict, tz_name: str, now: Optional[datetime] = None) -> str:
    tz = get_tz(tz_name)
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    future = [i for i in items if i["kind"] != "class" and from_iso(i["start"], tz) >= now - timedelta(hours=12)]
    soon = [i for i in future if from_iso(i["start"], tz) <= now + timedelta(days=14)]
    lines = [f"# {snapshot.get('term') or ''} 截止日期与考试".strip(), "",
             f"生成于 {fmt(now)}。时间均为 {tz_name}。", "", "## 未来两周", ""]
    lines += [f"- **{fmt(from_iso(i['start'], tz))}** {i['title']}"
              + (f"：{STATUS_TEXT.get(i.get('status'), '')}" if i["kind"] == "deadline" else f"（{i['kind']}）")
              for i in soon] or ["- 没有。"]
    lines += ["", "## 考试", ""]
    lines += [f"- **{fmt(from_iso(i['start'], tz))}** {i['title']}" + (f" · {i['location']}" if i.get("location") else "")
              + (f" · {i['weight']}" if i.get("weight") else "") for i in future if i["kind"] == "exam"] or ["- 还没有记录。让 AI 读课程大纲后写进 events.json。"]
    lines += ["", "## 全部待办（按时间）", ""]
    month = None
    for i in future:
        d = from_iso(i["start"], tz)
        if d.month != month:
            month = d.month
            lines += ["", f"### {d.year} 年 {d.month} 月", ""]
        mark = "✅" if i.get("done") else "⬜"
        lines.append(f"- {mark} {fmt(d)} · {i['title']}" + (f" · {i['detail']}" if i.get("detail") else ""))
    return "\n".join(lines) + "\n"


def render_course_md(course: dict, tz_name: str) -> str:
    tz = get_tz(tz_name)
    lines = [f"# {course['name']}", "", f"- 课站：{course.get('url')}", f"- NTULearn 课程编号：`{course.get('course_id')}`",
             f"- 已下载文件：{len([f for f in course.get('files', []) if not f.get('error')])} 个，在 `files/` 里",
             "- AI 整理的考核、政策和逐周内容写在同目录 `notes.md`（由 Claude Code 生成，见 README）", "",
             "## 成绩簿", "", "| 项目 | 截止 | 满分 | 状态 |", "|---|---|---|---|"]
    for col in sorted(course.get("columns", []), key=lambda x: x.get("due") or "9999"):
        due = parse_utc(col.get("due"))
        st = column_status(col)
        score = f" {_num(col.get('score'))}" if col.get("score") is not None else ""
        lines.append(f"| {col['name']} | {fmt(due.astimezone(tz)) if due else '—'} | {_num(col.get('possible')) or '—'} | {STATUS_TEXT[st]}{score} |")
    lines += ["", "## 公告", ""]
    for a in course.get("announcements", [])[:15]:
        created = parse_utc(a.get("created"))
        lines += [f"### {a.get('title')}  _{fmt(created.astimezone(tz)) if created else ''}_", "", (a.get("text") or "").strip(), ""]
    if not course.get("announcements"):
        lines += ["暂无。", ""]
    lines += ["## 课程内容结构", ""]
    for o in course.get("outline", []):
        link = f" · [正文]({'../../' + o['text_file']})" if o.get("text_file") else ""
        lines.append(f"{'  ' * o.get('depth', 0)}- {o.get('title')} `{o.get('type')}`{link}")
    return "\n".join(lines) + "\n"
