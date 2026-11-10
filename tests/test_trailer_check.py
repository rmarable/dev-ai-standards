"""Tests for checks/trailer_check.py: messages, ranges, pushes and the three exemptions.

P001 Verification, "A second trailer fails trailer_check in hook and CI ..." and the
exemption cases. Throwaway git repos in a temp dir.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from helpers import CLAUDE_TRAILER, CODEX_TRAILER, OUT, ZERO, commit, git, init_repo, msg, py

SCRIPT = OUT / "checks" / "trailer_check.py"
ROOT_SUBJECT = "new-claude-project: initial commit"


class TrailerCheck(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def check_msg(self, text: str) -> int:
        f = self.tmp / "MSG"
        f.write_text(text)
        return py(SCRIPT, "--message-file", str(f), cwd=self.tmp, home=self.home).returncode

    def tc(self, repo: Path, *args: str):
        return py(SCRIPT, "--repo", str(repo), *args, cwd=repo, home=self.home)

    def test_message_one_allowed_trailer_passes(self) -> None:
        self.assertEqual(self.check_msg(msg("Fix x")), 0)
        self.assertEqual(self.check_msg(msg("Fix x", CODEX_TRAILER)), 0)

    def test_message_two_trailers_fail(self) -> None:
        self.assertEqual(self.check_msg(f"Fix x\n\n{CLAUDE_TRAILER}\n{CODEX_TRAILER}\n"), 1)

    def test_message_model_name_or_none_fails(self) -> None:
        self.assertEqual(self.check_msg("Fix x\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"), 1)
        self.assertEqual(self.check_msg("Fix x\n"), 1)

    def test_message_comment_lines_ignored(self) -> None:
        self.assertEqual(self.check_msg(f"Fix x\n# {CLAUDE_TRAILER}\n"), 1)
        self.assertEqual(self.check_msg(f"Fix x\n\n{CLAUDE_TRAILER}\n# {CODEX_TRAILER}\n"), 0)

    def test_range_and_push(self) -> None:
        repo = init_repo(self.tmp / "r", self.home)
        a = commit(repo, self.home, msg("A"), {"a": "1"})
        git(repo, self.home, "switch", "-q", "-c", "feature")
        good = commit(repo, self.home, msg("B"), {"b": "1"})
        self.assertEqual(self.tc(repo, "--range", f"{a}..{good}").returncode, 0)
        bad = commit(repo, self.home, f"C\n\n{CLAUDE_TRAILER}\n{CLAUDE_TRAILER}", {"c": "1"})
        self.assertEqual(self.tc(repo, "--range", f"{a}..{bad}").returncode, 1)
        self.assertEqual(self.tc(repo, "--push", good, bad, "--ref", "refs/heads/feature").returncode, 1)
        self.assertEqual(self.tc(repo, "--commit", good).returncode, 0)

    def test_new_branch_skips_old_history_and_deletion_checks_nothing(self) -> None:
        repo = init_repo(self.tmp / "r", self.home)
        commit(repo, self.home, "old commit without trailer", {"a": "1"})
        git(repo, self.home, "switch", "-q", "-c", "feature")
        new = commit(repo, self.home, msg("new"), {"b": "1"})
        r = self.tc(repo, "--push", ZERO, new, "--ref", "refs/heads/feature", "--base-ref", "main")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("1 commit", r.stdout)
        r = self.tc(repo, "--push", new, ZERO, "--ref", "refs/heads/feature", "--base-ref", "main")
        self.assertEqual(r.returncode, 0)

    def test_launcher_root_commit_only_on_push_creating_main(self) -> None:
        repo = init_repo(self.tmp / "r", self.home)
        root = commit(repo, self.home, ROOT_SUBJECT, {"a": "1"})
        r = self.tc(repo, "--push", ZERO, root, "--ref", "refs/heads/main", "--base-ref", "main")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("exempt", r.stdout)
        later = commit(repo, self.home, ROOT_SUBJECT, {"b": "1"})
        r = self.tc(repo, "--push", ZERO, later, "--ref", "refs/heads/main", "--base-ref", "main")
        self.assertEqual(r.returncode, 1, "a non-root commit with the launcher subject must fail")

    def test_orphan_branch_root_with_launcher_subject_fails(self) -> None:
        repo = init_repo(self.tmp / "r", self.home)
        commit(repo, self.home, msg("A"), {"a": "1"})
        git(repo, self.home, "switch", "-q", "--orphan", "other")
        orphan = commit(repo, self.home, ROOT_SUBJECT, {"z": "1"})
        r = self.tc(repo, "--push", ZERO, orphan, "--ref", "refs/heads/other", "--base-ref", "main")
        self.assertEqual(r.returncode, 1)

    def test_dependabot_and_web_flow_need_verified_signatures(self) -> None:
        repo = init_repo(self.tmp / "r", self.home)
        base = commit(repo, self.home, msg("A"), {"a": "1"})
        git(repo, self.home, "switch", "-q", "-c", "dep")
        dep = commit(repo, self.home, "Bump x from 1 to 2", {"d": "1"})
        git(repo, self.home, "switch", "-q", "main")
        commit(repo, self.home, msg("B"), {"b": "1"})
        git(repo, self.home, "merge", "-q", "--no-ff", "-m", "Merge pull request #1", "dep")
        merge = git(repo, self.home, "rev-parse", "HEAD")
        meta = self.tmp / "meta.json"

        def run(data: dict[str, dict[str, object]]) -> int:
            meta.write_text(json.dumps(data))
            return self.tc(repo, "--range", f"{base}..{merge}", "--meta", str(meta)).returncode

        good = {
            dep: {"author_login": "dependabot[bot]", "committer_login": "web-flow", "verified": True},
            merge: {"author_login": "someone", "committer_login": "web-flow", "verified": True},
        }
        self.assertEqual(run(good), 0)
        self.assertEqual(run({**good, dep: {**good[dep], "verified": False}}), 1)
        self.assertEqual(run({**good, merge: {**good[merge], "verified": False}}), 1, "unsigned GitHub-named commit")


if __name__ == "__main__":
    unittest.main()
