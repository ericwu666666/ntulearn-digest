import argparse
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ntulearn_digest.cli import build_parser  # noqa: E402

SKILL = ROOT / ".claude" / "skills" / "ntulearn-digest" / "SKILL.md"
DOCS = ["AGENTS.md", "README.md", "README.en.md", ".claude/skills/ntulearn-digest/SKILL.md"]


def skill_body() -> str:
    _, _, body = SKILL.read_text(encoding="utf-8").split("---", 2)
    body = body.strip()
    assert body.startswith("# NTULearn digest")
    return body[len("# NTULearn digest"):].strip()


class AgentDocsTests(unittest.TestCase):
    def test_agents_md_matches_claude_skill(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        shared = re.search(r"<!-- shared-start[^>]*-->(.*?)<!-- shared-end -->", agents, re.S)
        self.assertIsNotNone(shared, "AGENTS.md lost its shared block markers")
        self.assertEqual(shared.group(1).strip(), skill_body(),
                         "AGENTS.md and SKILL.md drifted apart; copy the change to both")

    def test_documented_commands_exist(self):
        parser = build_parser()
        sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        for doc in DOCS:
            for cmd in re.findall(r"\bntulearn ([a-z]+)\b", (ROOT / doc).read_text(encoding="utf-8")):
                self.assertIn(cmd, sub.choices, f"{doc} mentions unknown command: ntulearn {cmd}")


if __name__ == "__main__":
    unittest.main()
