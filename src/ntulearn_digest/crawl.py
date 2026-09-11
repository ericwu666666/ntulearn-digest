"""Read everything useful from NTULearn for the current user and store it as a local snapshot.

Snapshot = courses + content outline + downloaded files + Ultra page text
         + gradebook columns with your own status + announcements.
"""
from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .client import ApiError, Blackboard
from .util import course_code, course_slug, html_to_text, safe_name, write_text

TERM_RE = re.compile(r"^(\d{2}S\d)-")
CONTAINERS = {"resource/x-bb-folder", "resource/x-bb-lesson"}
HAS_ATTACHMENTS = {
    "resource/x-bb-file", "resource/x-bb-document", "resource/x-bb-assignment",
    "resource/x-bb-lesson", "resource/x-bb-blti-link", "resource/x-bb-asmt-test-link",
}
NO_BODY = {"resource/x-bb-file", "resource/x-bb-folder"}
MAX_DEPTH = 12
Log = Callable[[str], None]


def term_of(course_id: Optional[str]) -> Optional[str]:
    m = TERM_RE.match(course_id or "")
    return m.group(1) if m else None


def list_courses(bb: Blackboard, term: Optional[str] = None, all_terms: bool = False,
                 only: Optional[List[str]] = None) -> Tuple[dict, List[dict], List[dict], Optional[str]]:
    """Return (me, active courses, dropped courses, chosen term)."""
    me = bb.get("users/me")
    uid = me["id"]
    rows = bb.paged(f"users/{uid}/courses", {"limit": 200, "expand": "course"})
    found = []
    for r in rows:
        c = r.get("course") or {}
        if not c or c.get("organization"):
            continue
        found.append({
            "id": c.get("id"),
            "course_id": c.get("courseId"),
            "name": c.get("name") or c.get("courseId"),
            "code": course_code(c.get("name"), c.get("courseId")),
            "term": term_of(c.get("courseId")),
            "role": r.get("courseRoleId"),
            "available": (c.get("availability") or {}).get("available") != "No"
            and (r.get("availability") or {}).get("available") != "No",
            "url": f"{bb.base_url}/ultra/courses/{c.get('id')}/outline",
        })
    terms = sorted({c["term"] for c in found if c["term"]})
    chosen = None if all_terms else (term or (terms[-1] if terms else None))
    if chosen:
        found = [c for c in found if c["term"] == chosen]
    if only:
        wanted = {x.upper() for x in only}
        found = [c for c in found if (c["code"] or "").upper() in wanted]

    def still_enrolled(c: dict) -> bool:
        return bb.get_or_none(f"courses/{c['id']}/users/{uid}") is not None

    with ThreadPoolExecutor(6) as pool:
        flags = list(pool.map(still_enrolled, found))
    active = [c for c, ok in zip(found, flags) if ok]
    dropped = [c for c, ok in zip(found, flags) if not ok]
    slugs: Dict[str, int] = {}
    for c in active:
        s = course_slug(c)
        if s in slugs:
            s = f"{s}-{c['id'].strip('_')}"
        slugs[s] = 1
        c["slug"] = s
    return me, active, dropped, chosen


def _children(bb: Blackboard, cid: str, nid: Optional[str]) -> List[dict]:
    path = f"courses/{cid}/contents" if nid is None else f"courses/{cid}/contents/{nid}/children"
    return bb.paged(path, {"limit": 200})


def _embedded_files(body: str) -> List[Tuple[str, str]]:
    """Files dropped into an Ultra document live in data-bbfile JSON with a short-lived signed URL."""
    out = []
    for m in re.finditer(r"<[a-z]+\b([^>]*?)data-bbfile=\"([^\"]+)\"([^>]*)>", body, flags=re.I):
        attrs = m.group(1) + m.group(3)
        try:
            info = json.loads(html.unescape(m.group(2)))
        except Exception:
            continue
        name = info.get("linkName") or info.get("displayName") or info.get("fileName") or "file"
        url = info.get("resourceUrl")
        if not url:
            href = re.search(r'(?:href|src)="([^"]+)"', attrs)
            url = html.unescape(href.group(1)) if href else None
        if url:
            out.append((name, url))
    return out


def _download(bb: Blackboard, url: str, dest: Path, auth: bool, root: Path) -> dict:
    rel = dest.relative_to(root).as_posix()
    if dest.exists() and dest.stat().st_size > 0:
        return {"path": rel, "new": False, "size": dest.stat().st_size}
    try:
        size = bb.download(url, dest, auth=auth)
        return {"path": rel, "new": True, "size": size}
    except ApiError as e:
        return {"path": rel, "error": f"HTTP {e.status}"}


def crawl_course(bb: Blackboard, course: dict, uid: str, out: Path, download: bool = True, workers: int = 4, log: Log = print) -> dict:
    cid = course["id"]
    cdir = out / "courses" / course["slug"]
    outline: List[dict] = []
    files: List[dict] = []
    errors: List[str] = []

    def handle(job: Tuple[dict, str, str, Optional[str]]) -> dict:
        node, folder, title, owner = job
        handler = (node.get("contentHandler") or {}).get("id", "")
        got: List[dict] = []
        text_file = None
        if download and handler in HAS_ATTACHMENTS:
            for a in bb.paged(f"courses/{cid}/contents/{node['id']}/attachments", {"limit": 100}):
                dest = cdir / "files" / folder / safe_name(a.get("fileName"))
                url = f"courses/{cid}/contents/{node['id']}/attachments/{a['id']}/download"
                got.append(_download(bb, url, dest, True, out))
        if handler not in NO_BODY:
            full = bb.get_or_none(f"courses/{cid}/contents/{node['id']}", {"fields": "id,title,body"}) or {}
            body = full.get("body") or ""
            if body:
                if download:
                    for name, url in _embedded_files(body):
                        got.append(_download(bb, url, cdir / "files" / folder / safe_name(name), False, out))
                text = html_to_text(body)
                if len(text) > 20:
                    page = cdir / "pages" / folder / (safe_name(title, 90) + ".md")
                    write_text(page, f"# {title}\n\n{text}\n")
                    text_file = page.relative_to(out).as_posix()
        return {"owner": owner, "files": got, "text_file": text_file}

    frontier: List[Tuple[Optional[str], str, int, str]] = [(None, "", 0, course["name"])]
    with ThreadPoolExecutor(workers) as pool:
        while frontier:
            def kids(f):
                try:
                    return f, _children(bb, cid, f[0])
                except ApiError as e:
                    errors.append(f"contents {f[1] or '/'}: HTTP {e.status}")
                    return f, []

            jobs: List[Tuple[dict, str, str, Optional[str]]] = []
            nxt: List[Tuple[Optional[str], str, int, str]] = []
            for (nid, path, depth, parent_title), children in pool.map(kids, frontier):
                for c in children:
                    title = c.get("title") or ""
                    handler = (c.get("contentHandler") or {}).get("id", "")
                    if title == "ultraDocumentBody":
                        jobs.append((c, path, parent_title, nid))
                        continue
                    name = safe_name(title, 90)
                    own = f"{path}/{name}" if path else name
                    container = own if (c.get("hasChildren") or handler in CONTAINERS) else path
                    params = (c.get("contentHandler") or {}).get("customParameters") or {}
                    outline.append({
                        "id": c.get("id"), "parent": nid, "depth": depth, "title": title,
                        "type": handler.replace("resource/x-bb-", ""), "path": own,
                        "created": c.get("created"), "modified": c.get("modified"),
                        "available": (c.get("availability") or {}).get("available"),
                        "due_hint": params.get("default_duedate"),
                    })
                    if handler in HAS_ATTACHMENTS or handler not in NO_BODY:
                        jobs.append((c, container, title, c.get("id")))
                    if c.get("hasChildren") and depth < MAX_DEPTH:
                        nxt.append((c["id"], own, depth + 1, title))
            by_id = {o["id"]: o for o in outline}
            for res in pool.map(handle, jobs):
                files.extend(res["files"])
                owner = by_id.get(res["owner"])
                if owner is not None and res["text_file"]:
                    owner["text_file"] = res["text_file"]
            frontier = nxt

    columns = []
    grades = {g.get("columnId"): g for g in bb.paged(f"courses/{cid}/gradebook/users/{uid}", {"limit": 200})}
    for col in bb.paged(f"courses/{cid}/gradebook/columns", {"limit": 200}):
        if (col.get("availability") or {}).get("available") == "No":
            continue
        g = grades.get(col.get("id")) or {}
        columns.append({
            "id": col.get("id"), "name": col.get("displayName") or col.get("name"),
            "due": (col.get("grading") or {}).get("due"), "possible": (col.get("score") or {}).get("possible"),
            "created": col.get("created"), "status": g.get("status"), "score": g.get("score"),
            "external": bool(col.get("externalGrade")),
        })
    announcements = [{
        "id": a.get("id"), "title": a.get("title"), "created": a.get("created"),
        "modified": a.get("modified"), "text": html_to_text(a.get("body")),
    } for a in bb.paged(f"courses/{cid}/announcements", {"limit": 100})]
    announcements.sort(key=lambda a: a.get("created") or "", reverse=True)

    new_files = sum(1 for f in files if f.get("new"))
    failed = [f for f in files if f.get("error")]
    log(f"  {course['code'] or course['name']}: {len(outline)} 项内容, {len(files)} 个文件（新 {new_files}，失败 {len(failed)}）, "
        f"{len(columns)} 个成绩项, {len(announcements)} 条公告")
    return {**course, "outline": outline, "files": files, "columns": columns,
            "announcements": announcements, "errors": errors}


def sync(bb: Blackboard, out: Path, term: Optional[str] = None, all_terms: bool = False,
         download: bool = True, workers: int = 4, log: Log = print, only: Optional[List[str]] = None) -> dict:
    me, active, dropped, chosen = list_courses(bb, term, all_terms, only)
    log(f"学期 {chosen or '全部'}：{len(active)} 门课" + (f"，{len(dropped)} 门已退选" if dropped else ""))
    courses = [crawl_course(bb, c, me["id"], out, download, workers, log) for c in active]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_url": bb.base_url,
        "term": chosen,
        "courses": courses,
        "dropped": [{k: c.get(k) for k in ("id", "course_id", "name", "code")} for c in dropped],
    }
