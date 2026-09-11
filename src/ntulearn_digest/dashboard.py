"""A calm, phone-friendly HTML dashboard. One self-contained file with its own charset."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape as e
from typing import List, Optional

from .report import STATUS_TEXT, _num, column_status, fmt
from .util import from_iso, get_tz, parse_utc

CSS = """
:root{--paper:#F7F6F2;--card:#fff;--card2:#F1F0EB;--ink:#26251F;--ink2:#5F5D55;--ink3:#8E8B82;--rule:#E4E2DB;
--accent:#3A5F8A;--accent-bg:#E6EEF6;--urgent:#B7422B;--urgent-bg:#F9E8E3;--soon:#946312;--soon-bg:#F8EEDA;--ok:#3B7A57;--ok-bg:#E3F0E8;
--shadow:0 1px 2px rgba(38,37,31,.05),0 6px 18px -12px rgba(38,37,31,.25)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#17181A;--card:#1F2124;--card2:#26292D;--ink:#EAE8E2;--ink2:#B4B1A8;--ink3:#85827A;--rule:#33363B;
--accent:#8FB4DA;--accent-bg:#233241;--urgent:#F08C74;--urgent-bg:#3E2620;--soon:#E0B45A;--soon-bg:#3A2F17;--ok:#7FC49A;--ok-bg:#1F352A;--shadow:none}}
:root[data-theme="dark"]{--paper:#17181A;--card:#1F2124;--card2:#26292D;--ink:#EAE8E2;--ink2:#B4B1A8;--ink3:#85827A;--rule:#33363B;
--accent:#8FB4DA;--accent-bg:#233241;--urgent:#F08C74;--urgent-bg:#3E2620;--soon:#E0B45A;--soon-bg:#3A2F17;--ok:#7FC49A;--ok-bg:#1F352A;--shadow:none}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.75 "Noto Sans SC","PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif;
-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
.page{max-width:760px;margin:0 auto;padding:36px 20px 96px}h1,h2,h3{font-family:"Noto Serif SC","Songti SC",Georgia,serif;margin:0}
h1{font-size:32px;line-height:1.25}h2{font-size:21px;margin:0 0 14px}h3{font-size:16.5px}p{margin:0}
.sub{margin-top:8px;font-size:15px;color:var(--ink2)}.top{padding-bottom:22px;border-bottom:1px solid var(--rule)}
.stats{display:flex;gap:28px;flex-wrap:wrap;margin-top:18px}.stats b{display:block;font-size:22px;line-height:1.1}.stats span{font-size:13px;color:var(--ink3)}
section{margin-top:46px}.note{font-size:14px;color:var(--ink3);margin:-8px 0 14px}
.card{background:var(--card);border:1px solid var(--rule);border-radius:10px;box-shadow:var(--shadow)}
.list{display:flex;flex-direction:column;gap:10px}.row{display:flex;gap:16px;padding:14px 16px;align-items:flex-start}
.date{flex:0 0 72px;text-align:center;border-radius:8px;padding:7px 4px;background:var(--card2);line-height:1.15}
.date b{display:block;font-size:20px}.date span{display:block;font-size:12px;color:var(--ink3);margin-top:3px}
.date.urgent{background:var(--urgent-bg)}.date.urgent b{color:var(--urgent)}.date.soon{background:var(--soon-bg)}.date.soon b{color:var(--soon)}
.date.ok{background:var(--ok-bg)}.date.ok b{color:var(--ok)}
.body{flex:1;min-width:0}.t{font-weight:700;line-height:1.45}.c{color:var(--accent);margin-right:6px}.d{margin-top:3px;font-size:14.5px;color:var(--ink2);line-height:1.65}
.tag{display:inline-block;font-size:12.5px;padding:0 8px;border-radius:999px;margin-left:6px;font-weight:500;vertical-align:1px}
.tag.urgent{background:var(--urgent-bg);color:var(--urgent)}.tag.soon{background:var(--soon-bg);color:var(--soon)}.tag.ok{background:var(--ok-bg);color:var(--ok)}
.tbl{padding:4px 14px;overflow-x:auto}table{width:100%;border-collapse:collapse}td{padding:10px 6px;border-bottom:1px solid var(--rule);vertical-align:top;font-size:15px}
tr:last-child td{border-bottom:none}td.when{white-space:nowrap;color:var(--ink2);width:118px}td.st{white-space:nowrap;text-align:right;font-size:13.5px;color:var(--ink3)}
.done td{color:var(--ink3)}.month{margin:22px 0 8px;font-size:15px;color:var(--ink2);font-weight:600}
.courses{display:grid;gap:12px;grid-template-columns:1fr}@media(min-width:640px){.courses{grid-template-columns:1fr 1fr}}
.course{padding:16px 18px}.course .code{font-weight:700;color:var(--accent)}.course .name{font-size:14.5px;color:var(--ink2)}
.course ul{margin:8px 0 0;padding-left:18px;font-size:14px;color:var(--ink2)}.course li{margin:2px 0}
.change{padding:14px 18px}.change ul{margin:6px 0 0;padding-left:18px;font-size:14.5px;color:var(--ink2)}
a{color:var(--accent)}footer{margin-top:60px;padding-top:16px;border-top:1px solid var(--rule);font-size:13px;color:var(--ink3);line-height:1.8}
"""


def _date_box(dt: datetime, cls: str) -> str:
    return f'<div class="date {cls}"><b>{dt.month}/{dt.day}</b><span>周{"一二三四五六日"[dt.weekday()]} {dt:%H:%M}</span></div>'


def render_dashboard(snapshot: dict, items: List[dict], diff: Optional[dict], tz_name: str,
                     now: Optional[datetime] = None) -> str:
    tz = get_tz(tz_name)
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    courses = snapshot.get("courses", [])
    future = [i for i in items if i["kind"] != "class" and from_iso(i["start"], tz) >= now - timedelta(hours=6)]
    soon = [i for i in future if from_iso(i["start"], tz) <= now + timedelta(days=14)]
    exams = [i for i in future if i["kind"] == "exam"]
    todo = [i for i in future if i["kind"] == "deadline" and not i.get("done")]
    synced = from_iso(snapshot.get("generated_at"))
    term = snapshot.get("term") or ""
    out = [f'<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
           f'<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>{e(term)} 学期看板</title>\n'
           f'<style>{CSS}</style>\n</head>\n<body>\n<div class="page">']
    out.append(f'<header class="top"><h1>{e(term)} 学期看板</h1><p class="sub">数据来自 NTULearn，'
               f'{e(fmt(synced.astimezone(tz)) if synced else "—")} 同步。时间均为 {e(tz_name)}。状态直接读自成绩簿。</p>'
               f'<div class="stats"><div><b>{len(courses)}</b><span>门课</span></div><div><b>{len(todo)}</b><span>项未完成截止</span></div>'
               f'<div><b>{len(exams)}</b><span>场考试</span></div>'
               f'<div><b>{sum(len([f for f in c.get("files", []) if not f.get("error")]) for c in courses)}</b><span>个文件</span></div></div></header>')

    out.append('<section><h2>未来两周</h2><p class="note">按时间排序。没提交且三天内截止的标红。</p><div class="list">')
    for i in soon:
        dt = from_iso(i["start"], tz)
        days = (dt - now).total_seconds() / 86400
        if i.get("done"):
            cls, tag = "ok", f'<span class="tag ok">{e(STATUS_TEXT.get(i.get("status"), "已完成"))}</span>'
        elif i["kind"] == "exam":
            cls, tag = "urgent" if days <= 7 else "soon", '<span class="tag urgent">考试</span>'
        else:
            cls = "urgent" if days <= 3 else "soon"
            tag = f'<span class="tag {cls}">{e(STATUS_TEXT.get(i.get("status"), i["kind"]))}</span>' if i["kind"] == "deadline" else ""
        if i["kind"] == "deadline":
            parts = [f"满分 {_num(i.get('possible'))}" if i.get("possible") else "",
                     f"得分 {_num(i.get('score'))}" if i.get("score") is not None else ""]
        else:
            parts = [i.get("detail"), i.get("location"), i.get("weight")]
        line = " · ".join(x for x in parts if x)
        out.append(f'<div class="card row">{_date_box(dt, cls)}<div class="body"><p class="t"><span class="c">{e(i.get("course", ""))}</span>'
                   f'{e(i.get("name") or i["title"])} {tag}</p><p class="d">{e(line)}</p></div></div>')
    if not soon:
        out.append('<p class="d">未来两周没有截止日期。</p>')
    out.append('</div></section>')

    out.append('<section><h2>考试</h2><div class="list">')
    for i in exams:
        dt = from_iso(i["start"], tz)
        extra = " · ".join(x for x in [i.get("location"), i.get("weight")] if x)
        out.append(f'<div class="card row">{_date_box(dt, "soon")}<div class="body"><p class="t"><span class="c">{e(i.get("course", ""))}</span>'
                   f'{e(i.get("name") or i["title"])}</p><p class="d">{e(extra)}{"<br>" if extra and i.get("detail") else ""}{e(i.get("detail", ""))}</p></div></div>')
    if not exams:
        out.append('<p class="d">还没有考试记录。考试时间通常只写在课程大纲 PDF 里：让 Claude Code 读大纲后写进 events.json，再运行 build。</p>')
    out.append('</div></section>')

    if diff and not diff.get("first_run") and (diff.get("courses") or diff.get("added_courses") or diff.get("dropped_courses")):
        out.append('<section><h2>上次同步以来的变化</h2><div class="list">')
        for c in diff.get("courses", []):
            bullets = [f"📢 {a['title']}" for a in c["new_announcements"]]
            bullets += [f"🆕 成绩项：{col['name']}" for col in c["new_columns"]]
            bullets += [f"⏰ 截止时间变了：{d['name']}" for d in c["due_changed"]]
            bullets += [f"✅ {g['name']}：{STATUS_TEXT[column_status(g)]}" for g in c["grade_changed"]]
            if c["new_files"]:
                bullets.append(f"📥 新文件 {len(c['new_files'])} 个")
            out.append(f'<div class="card change"><h3>{e(c.get("code") or c.get("name"))}</h3><ul>'
                       + "".join(f"<li>{e(b)}</li>" for b in bullets) + "</ul></div>")
        for label, key in (("新增课程", "added_courses"), ("消失的课程，可能已退选", "dropped_courses")):
            if diff.get(key):
                out.append(f'<div class="card change"><h3>{label}</h3><ul>' + "".join(f"<li>{e(n)}</li>" for n in diff[key]) + "</ul></div>")
        out.append('</div></section>')

    out.append('<section><h2>各门课</h2><div class="courses">')
    for c in courses:
        cols = c.get("columns", [])
        counts = {k: sum(1 for col in cols if column_status(col) == k) for k in ("graded", "submitted", "todo")}
        nxt = next((i for i in todo if i.get("course") == (c.get("code") or c.get("name"))), None)
        anns = "".join(f"<li>{e(a['title'] or '')} <span style='color:var(--ink3)'>{e(fmt(parse_utc(a['created']).astimezone(tz), False) if parse_utc(a.get('created')) else '')}</span></li>"
                       for a in c.get("announcements", [])[:3])
        out.append(f'<div class="card course"><p><span class="code">{e(c.get("code") or "")}</span> '
                   f'<a href="{e(c.get("url") or "#")}">课站</a></p><p class="name">{e(c.get("name") or "")}</p>'
                   f'<p class="d">成绩项：已评分 {counts["graded"]} · 待批改 {counts["submitted"]} · 未见提交 {counts["todo"]}</p>'
                   + (f'<p class="d">下一个截止：{e(fmt(from_iso(nxt["start"], tz)))} {e(nxt["name"])}</p>' if nxt else "")
                   + (f"<ul>{anns}</ul>" if anns else "") + "</div>")
    out.append('</div></section>')

    out.append('<section><h2>全部截止日期</h2><div class="card tbl">')
    month = None
    rows = []
    for i in future:
        dt = from_iso(i["start"], tz)
        if dt.month != month:
            if rows:
                out.append("<table>" + "".join(rows) + "</table>")
                rows = []
            month = dt.month
            out.append(f'<p class="month">{dt.year} 年 {dt.month} 月</p>')
        st = STATUS_TEXT.get(i.get("status"), "考试" if i["kind"] == "exam" else "")
        rows.append(f'<tr class="{"done" if i.get("done") else ""}"><td class="when">{e(fmt(dt))}</td>'
                    f'<td><span class="c">{e(i.get("course", ""))}</span>{e(i.get("name") or i["title"])}</td><td class="st">{e(st)}</td></tr>')
    if rows:
        out.append("<table>" + "".join(rows) + "</table>")
    out.append('</div></section>')
    out.append('<footer>由 <a href="https://github.com/ericwu666666/ntulearn-digest">ntulearn-digest</a> 生成。'
               '非 NTU 官方工具，一切以 NTULearn 和老师通知为准。</footer></div>\n</body>\n</html>\n')
    return "\n".join(out)
