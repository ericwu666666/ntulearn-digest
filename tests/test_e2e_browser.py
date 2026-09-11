"""End to end: real Chrome/Edge (headless) logs in to a mock NTULearn, then sync runs over real HTTP."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mock_ntulearn import MockNTULearn  # noqa: E402
from ntulearn_digest import cli  # noqa: E402
from ntulearn_digest.browser import find_browser  # noqa: E402


@unittest.skipUnless(find_browser(), "needs Chrome, Edge or Chromium")
@unittest.skipIf(os.environ.get("NTULEARN_SKIP_BROWSER_TEST"), "browser test disabled")
class BrowserEndToEnd(unittest.TestCase):
    def test_go_logs_in_and_syncs(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            with MockNTULearn() as mock:
                args = ["go", "--base-url", mock.base, "--headless", "--timeout", "60", "--profile", str(tmp / "profile"),
                        "--token-file", str(tmp / "token"), "-o", str(tmp / "out"), "--no-open"]
                self.assertEqual(cli.main(args), 0)
                self.assertEqual((tmp / "token").read_text(encoding="utf-8"), mock.token)
                snap = json.loads((tmp / "out" / "snapshot.json").read_text(encoding="utf-8"))
                self.assertEqual([c["code"] for c in snap["courses"]], ["ZX1001"])
                self.assertEqual([c["code"] for c in snap["dropped"]], ["ZX2002"])
                files = tmp / "out" / "courses" / snap["courses"][0]["slug"] / "files" / "Week 1"
                self.assertEqual((files / "Lecture 1.pdf").read_bytes(), b"%PDF-1.4 lecture")
                self.assertEqual((files / "Course Info" / "Embedded.pdf").read_bytes(), b"%PDF-1.4 embedded")
                self.assertIn(("/signed/embedded.pdf", False), mock.hits)
                self.assertEqual(sum(1 for p, _ in mock.hits if p.endswith("/announcements")), 2)
                self.assertTrue((tmp / "out" / "dashboard.html").exists())
                hits_before = len(mock.hits)
                self.assertEqual(cli.main(args), 0)
                self.assertFalse(any(p == "/ultra/course" for p, _ in mock.hits[hits_before:]),
                                 "a still-valid token must not open the browser again")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
