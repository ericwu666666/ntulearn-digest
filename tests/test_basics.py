import base64
import json
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ntulearn_digest.auth import AuthError, jwt_expiry, normalize_token  # noqa: E402
from ntulearn_digest.calendar_ics import build_calendar, escape  # noqa: E402
from ntulearn_digest.report import collect_items, diff_snapshots  # noqa: E402
from ntulearn_digest.schedule import class_meetings, parse_schedule, parse_weeks, select_rows, teaching_week_monday  # noqa: E402
from ntulearn_digest.util import course_slug, html_to_text, safe_name  # noqa: E402


def fake_jwt(exp: int) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{enc({'alg': 'none'})}.{enc({'exp': exp})}.sig"


class UtilTests(unittest.TestCase):
    def test_safe_name_keeps_extension(self):
        name = safe_name("a" * 200 + ".pdf")
        self.assertTrue(name.endswith(".pdf"))
        self.assertLessEqual(len(name), 120)
        self.assertEqual(safe_name('Week 1: "Intro"/Slides?'), "Week 1_ _Intro__Slides_")

    def test_course_slug(self):
        self.assertEqual(course_slug({"name": "HE3001-MICROECONOMICS III AY26/27 Sem 1 Main"}), "HE3001-Microeconomics-III-Main")

    def test_html_to_text(self):
        self.assertEqual(html_to_text("<p>Hi&nbsp;there</p><ul><li>One</li></ul>"), "Hi there\n- One")


class AuthTests(unittest.TestCase):
    def test_accepts_jwt_bearer_json_and_storage_value(self):
        jwt = fake_jwt(2_000_000_000)
        storage = base64.b64encode(json.dumps({"accessToken": jwt, "expiresIn": 3600}).encode()).decode()
        for raw in (jwt, f"Bearer {jwt}", json.dumps({"accessToken": jwt}), storage, f'"{storage}"'):
            self.assertEqual(normalize_token(raw), jwt)
        self.assertEqual(jwt_expiry(jwt), datetime.fromtimestamp(2_000_000_000, tz=timezone.utc))

    def test_rejects_garbage(self):
        with self.assertRaises(AuthError):
            normalize_token("hello world")


class CalendarTests(unittest.TestCase):
    def test_folding_escaping_and_deadline_block(self):
        items = [{"uid": "x1", "kind": "deadline", "title": "HE3001 Quiz 2，" + "很长的中文标题" * 10,
                  "start": "2026-09-20T23:59:00+08:00", "detail": "a;b,c\nd"}]
        ics = build_calendar(items, "测试", now=datetime(2026, 9, 1, tzinfo=timezone.utc))
        for line in ics.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)
        unfolded = ics.replace("\r\n ", "")
        self.assertIn("DTSTART:20260920T152900Z", unfolded)
        self.assertIn("DTEND:20260920T155900Z", unfolded)
        self.assertIn("TRIGGER:-P1D", unfolded)
        self.assertEqual(escape("a;b,c\nd"), "a\\;b\\,c\\nd")


SAMPLE = """
<table><tr><TD WIDTH="100"><B>ZX1001</B></TD><TD><B>DEMO COURSE~</B></TD><TD><B> 3.0 AU</B></TD></tr></table>
<table border><tr><th>INDEX</th><th>TYPE</th><th>GROUP</th><th>DAY</th><th>TIME</th><th>VENUE</th><th>REMARK</th></tr>
<TR><td><b>11111</b></td><td><b>LEC/STUDIO</b></td><td><b>LEC1</b></td><td><b>THU</b></td><td><b>1530-1720</b></td><td><b>LT5</b></td><td><b></b></td></tr>
<TR><td><b></b></td><td><b>TUT</b></td><td><b>T8</b></td><td><b>WED</b></td><td><b>0930-1020</b></td><td><b>TR+96</b></td><td><b>Teaching Wk2-13</b></td></tr>
<TR><td><b>22222</b></td><td><b>LEC/STUDIO</b></td><td><b>LEC1</b></td><td><b>THU</b></td><td><b>1530-1720</b></td><td><b>LT5</b></td><td><b></b></td></tr>
</table>"""


class ScheduleTests(unittest.TestCase):
    def test_parse_and_expand(self):
        rows = parse_schedule(SAMPLE)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["index"], "11111")
        picked = select_rows(rows, "ZX1001", index="11111")
        self.assertEqual([r["group"] for r in picked], ["LEC1", "T8"])
        meetings = class_meetings(picked, date(2026, 8, 10))
        self.assertEqual(len(meetings), 13 + 12)
        self.assertTrue(all(m["start"][:10] < "2026-09-28" or m["start"][:10] > "2026-10-02" for m in meetings))

    def test_weeks(self):
        self.assertEqual(parse_weeks("Teaching Wk2-7,9-13"), [2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13])
        self.assertEqual(parse_weeks(""), list(range(1, 14)))
        self.assertEqual(teaching_week_monday(date(2026, 8, 10), 8), date(2026, 10, 5))


class ReportTests(unittest.TestCase):
    def test_items_and_diff(self):
        old = {"courses": [{"id": "c", "code": "ZX1001", "name": "n", "outline": [], "files": [],
                            "columns": [{"id": "q1", "name": "Quiz 1", "due": "2026-09-06T15:59:00.000Z", "status": None, "score": None}],
                            "announcements": []}]}
        new = json.loads(json.dumps(old))
        new["courses"][0]["columns"][0].update(status="Graded", score=90, possible=100)
        new["courses"][0]["columns"].append({"id": "q2", "name": "Quiz 2", "due": "2026-09-20T15:59:00.000Z", "possible": 100})
        new["courses"][0]["announcements"].append({"id": "a", "title": "Quiz 2 open", "created": "2026-09-10T01:00:00.000Z"})
        d = diff_snapshots(old, new)["courses"][0]
        self.assertEqual([c["name"] for c in d["new_columns"]], ["Quiz 2"])
        self.assertEqual(d["grade_changed"][0]["score"], 90)
        self.assertEqual(len(d["new_announcements"]), 1)
        items = collect_items(new, [{"course": "ZX1001", "title": "Midterm Test", "start": "2026-09-24T15:30"}], [])
        self.assertEqual([i["kind"] for i in items], ["deadline", "deadline", "exam"])
        self.assertTrue(items[0]["done"])
        self.assertEqual(items[0]["start"], "2026-09-06T23:59:00+08:00")


if __name__ == "__main__":
    unittest.main()
