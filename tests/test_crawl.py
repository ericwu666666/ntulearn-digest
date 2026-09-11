import html
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ntulearn_digest import cli  # noqa: E402
from ntulearn_digest.client import ApiError  # noqa: E402
from ntulearn_digest.crawl import sync  # noqa: E402


class FakeBlackboard:
    """Answers the same calls as client.Blackboard from an in-memory table."""

    base_url = "https://ntulearn.example.edu"

    def __init__(self):
        self.requests = 0
        bbfile = html.escape(json.dumps({"linkName": "Embedded.pdf", "resourceUrl": "https://files.example/signed"}), quote=True)
        img = html.escape(json.dumps({"displayName": "diagram.png", "resourceUrl": ""}), quote=True)
        self.routes = {
            "users/me": {"id": "u1", "name": {"given": "Test"}},
            "users/u1/courses": [
                {"course": {"id": "_1_1", "courseId": "26S1-ZX1001-LEC", "name": "ZX1001-DEMO COURSE AY26/27 Sem 1 Main"}},
                {"course": {"id": "_2_1", "courseId": "26S1-ZX2002-LEC", "name": "ZX2002-DROPPED COURSE Main"}},
                {"course": {"id": "_3_1", "courseId": "25S2-ZX0001-LEC", "name": "ZX0001-OLD COURSE Main"}},
            ],
            "courses/_1_1/users/u1": {"userId": "u1"},
            "courses/_1_1/contents": [{"id": "f1", "title": "Week 1", "hasChildren": True, "contentHandler": {"id": "resource/x-bb-folder"}}],
            "courses/_1_1/contents/f1/children": [
                {"id": "file1", "title": "Slides", "contentHandler": {"id": "resource/x-bb-file"}},
                {"id": "doc1", "title": "Course Info", "hasChildren": True, "contentHandler": {"id": "resource/x-bb-document"}},
            ],
            "courses/_1_1/contents/doc1/children": [{"id": "body1", "title": "ultraDocumentBody", "contentHandler": {"id": "resource/x-bb-document"}}],
            "courses/_1_1/contents/file1/attachments": [{"id": "att1", "fileName": "Lecture 1.pdf"}],
            "courses/_1_1/contents/doc1/attachments": [],
            "courses/_1_1/contents/doc1": {"id": "doc1"},
            "courses/_1_1/contents/body1": {"id": "body1", "body": f'<p>The midterm is on 21 Sep, worth 20%.</p><a data-bbfile="{bbfile}" href="#">x</a>'
                                                            f'<img src="https://files.example/img-signed" data-bbfile="{img}">'},
            "courses/_1_1/gradebook/columns": [{"id": "q1", "name": "Quiz 1", "grading": {"due": "2026-09-06T15:59:00.000Z"}, "score": {"possible": 100}}],
            "courses/_1_1/gradebook/users/u1": [{"columnId": "q1", "status": "Graded", "score": 95}],
            "courses/_1_1/announcements": [{"id": "an1", "title": "Welcome", "created": "2026-08-01T01:00:00.000Z", "body": "<p>Hello</p>"}],
        }
        self.downloads = []

    def _find(self, path):
        self.requests += 1
        if path not in self.routes:
            raise ApiError(404, path)
        return self.routes[path]

    def get(self, path, params=None):
        return self._find(path)

    def get_or_none(self, path, params=None, missing=(403, 404)):
        try:
            return self._find(path)
        except ApiError:
            return None

    def paged(self, path, params=None, missing=(403, 404)):
        try:
            return list(self._find(path))
        except ApiError:
            return []

    def download(self, url, dest, auth=True):
        self.downloads.append((url, auth))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"%PDF-1.4 fake")
        return 13


class CrawlTests(unittest.TestCase):
    def test_sync_end_to_end_with_fake_api(self):
        bb = FakeBlackboard()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            snap = sync(bb, out, log=lambda m: None)
            self.assertEqual(snap["term"], "26S1")
            self.assertEqual([c["code"] for c in snap["courses"]], ["ZX1001"])
            self.assertEqual([c["code"] for c in snap["dropped"]], ["ZX2002"])
            course = snap["courses"][0]
            paths = sorted(f["path"] for f in course["files"])
            slug = course["slug"]
            self.assertEqual(paths, [f"courses/{slug}/files/Week 1/Course Info/Embedded.pdf",
                                     f"courses/{slug}/files/Week 1/Course Info/diagram.png",
                                     f"courses/{slug}/files/Week 1/Lecture 1.pdf"])
            self.assertIn(("https://files.example/img-signed", False), bb.downloads)
            self.assertIn(("https://files.example/signed", False), bb.downloads)
            info = next(o for o in course["outline"] if o["id"] == "doc1")
            self.assertTrue((out / info["text_file"]).read_text(encoding="utf-8").startswith("# Course Info"))
            self.assertEqual(course["columns"][0]["score"], 95)
            self.assertEqual(sync(bb, out, log=lambda m: None, only=["ZX9999"])["courses"], [])
            again = sync(bb, out, log=lambda m: None)
            self.assertFalse(any(f.get("new") for f in again["courses"][0]["files"]))

    def test_demo_command_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cli.main(["demo", "-o", tmp]), 0)
            for name in ("calendar.ics", "dashboard.html", "deadlines.md", "changes.md", "items.json"):
                self.assertTrue((Path(tmp) / name).stat().st_size > 100, name)
            page = (Path(tmp) / "dashboard.html").read_text(encoding="utf-8")
            self.assertIn('<meta charset="utf-8">', page[:300])
            self.assertEqual(cli.main(["build", "-o", tmp]), 0)


if __name__ == "__main__":
    unittest.main()
