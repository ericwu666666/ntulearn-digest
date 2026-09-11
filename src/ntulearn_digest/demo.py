"""Fictional data so anyone can preview the outputs without an NTU account."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from .schedule import class_meetings


def _z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def demo_data(now: datetime) -> Tuple[dict, dict, List[dict], List[dict]]:
    """Return (old snapshot, new snapshot, events, class meetings) around ``now`` (aware, local time)."""
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def at(days: int, hh: int, mm: int = 0) -> str:
        return _z(day + timedelta(days=days, hours=hh, minutes=mm))

    base = "https://ntulearn.example.edu"
    courses = [
        {"id": "_1001_1", "course_id": "99S1-ZX1001-LEC", "code": "ZX1001", "name": "ZX1001-GAME THEORY FOR DEMO Main",
         "slug": "ZX1001-Game-Theory-For-Demo-Main", "term": "99S1",
         "columns": [
             {"id": "c1", "name": "Quiz 1", "due": at(-3, 23, 59), "possible": 100, "status": "Graded", "score": 90},
             {"id": "c2", "name": "Quiz 2", "due": at(2, 23, 59), "possible": 100, "status": None, "score": None},
             {"id": "c3", "name": "Problem Set 3", "due": at(9, 10), "possible": 10, "status": None, "score": None}],
         "announcements": [
             {"id": "a1", "title": "Quiz 2 is now open", "created": at(-1, 9), "text": "Quiz 2 covers lectures 4 and 5."},
             {"id": "a2", "title": "Welcome to the course", "created": at(-30, 9), "text": "Slides are in the Content folder."}]},
        {"id": "_1002_1", "course_id": "99S1-ZX2002-LEC", "code": "ZX2002", "name": "ZX2002-DATA SCIENCE BASICS Main",
         "slug": "ZX2002-Data-Science-Basics-Main", "term": "99S1",
         "columns": [
             {"id": "d1", "name": "Assignment 3", "due": at(-1, 10), "possible": 4, "status": "NeedsGrading", "score": None},
             {"id": "d2", "name": "Assignment 4", "due": at(5, 10), "possible": 4, "status": None, "score": None},
             {"id": "d3", "name": "Project Proposal", "due": at(26, 10), "possible": 4, "status": None, "score": None}],
         "announcements": [{"id": "b1", "title": "Assignment 4 released", "created": at(-2, 21), "text": "Question 2 uses a Markov chain simulation."}]},
        {"id": "_1003_1", "course_id": "99S1-ZX3003-LEC", "code": "ZX3003", "name": "ZX3003-STOCHASTIC MODELS Main",
         "slug": "ZX3003-Stochastic-Models-Main", "term": "99S1",
         "columns": [{"id": "e1", "name": "Homework 1", "due": at(12, 23, 59), "possible": 30, "status": None, "score": None}],
         "announcements": [{"id": "f1", "title": "Midterm information", "created": at(-4, 13), "text": "The midterm covers weeks 1 to 4."}]},
    ]
    for c in courses:
        c["url"] = f"{base}/ultra/courses/{c['id']}/outline"
        c["files"] = [{"path": f"courses/{c['slug']}/files/Week 1/Lecture 1.pdf", "size": 1024, "new": False},
                      {"path": f"courses/{c['slug']}/files/Week 5/Lecture 5.pdf", "size": 2048, "new": True}]
        c["outline"] = [{"id": c["id"] + "w1", "parent": None, "depth": 0, "title": "Week 1", "type": "folder", "path": "Week 1"},
                        {"id": c["id"] + "l1", "parent": c["id"] + "w1", "depth": 1, "title": "Lecture 1.pdf", "type": "file", "path": "Week 1/Lecture 1.pdf"},
                        {"id": c["id"] + "w5", "parent": None, "depth": 0, "title": "Week 5", "type": "folder", "path": "Week 5"}]
        c["errors"] = []
    new = {"generated_at": _z(now), "base_url": base, "term": "99S1", "courses": courses, "dropped": []}

    old = copy.deepcopy(new)
    old["generated_at"] = _z(now - timedelta(days=4))
    for c in old["courses"]:
        c["announcements"] = c["announcements"][1:]
        c["outline"] = c["outline"][:2]
        for f in c["files"]:
            f["new"] = False
    old["courses"][1]["columns"] = old["courses"][1]["columns"][:1]
    old["courses"][1]["columns"][0]["status"] = None
    old["courses"][0]["columns"][0]["status"], old["courses"][0]["columns"][0]["score"] = None, None

    def local(days: int, hh: int, mm: int = 0) -> str:
        return (day + timedelta(days=days, hours=hh, minutes=mm)).replace(tzinfo=None).isoformat(timespec="minutes")

    events = [
        {"course": "ZX3003", "title": "Midterm", "kind": "exam", "start": local(10, 9, 45), "end": local(10, 11),
         "location": "LT25", "weight": "20%", "detail": "Weeks 1–4 and tutorials 1–4. One A4 help sheet allowed.",
         "source": "Midterm Information.pdf"},
        {"course": "ZX2002", "title": "Midterm Quiz", "kind": "exam", "start": local(11, 11, 30), "end": local(11, 14, 20),
         "location": "LT23", "weight": "30%", "detail": "Closed book, no AI.", "source": "Lecture 1 slides p.8"},
        {"course": "ZX1001", "title": "Bi-semester Test 1", "kind": "exam", "start": local(13, 15, 30), "end": local(13, 17, 20),
         "location": "LT5", "weight": "30%", "source": "Course introduction"},
    ]
    monday = (day - timedelta(days=day.weekday() + 7 * 4)).date()
    rows = [
        {"code": "ZX1001", "title": "GAME THEORY FOR DEMO", "index": "1", "type": "LEC/STUDIO", "group": "LEC1",
         "day": "THU", "start": "15:30", "end": "17:20", "venue": "LT5", "remark": ""},
        {"code": "ZX2002", "title": "DATA SCIENCE BASICS", "index": "2", "type": "SEM", "group": "SEM1",
         "day": "TUE", "start": "11:30", "end": "14:20", "venue": "TR+56", "remark": ""},
        {"code": "ZX3003", "title": "STOCHASTIC MODELS", "index": "3", "type": "TUT", "group": "T1",
         "day": "FRI", "start": "10:30", "end": "11:20", "venue": "LT1", "remark": "Teaching Wk2-13"},
    ]
    return old, new, events, class_meetings(rows, monday)
