"""Tests for bin/gate-status: docs-only decisions from the base branch's script and list.

P001 Verification, "Enforcement": docs only only for docs-only PRs; refuses a dirty tree or stale
head; refuses a PR that renames a script under a docs path, and one that widens the docs-only
list (the base branch's list decides). Offline: a fake `gh`, a local bare `origin`, --dry-run.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import GateStatusRunner, apply, commit, git, init_repo, make_kit, msg


class GateStatus(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        kit = make_kit(self.tmp)
        self.repo = init_repo(self.tmp / "repo", self.home)
        r = apply(kit, self.repo, self.home, "--high-stakes")
        self.assertEqual(r.returncode, 0, r.stderr)
        commit(
            self.repo,
            self.home,
            msg("Apply standards"),
            {"src/tool.py": "print(1)\n", "planning-docs/a.md": "a\n"},
        )
        self.runner = GateStatusRunner(self.tmp, self.home, self.repo)
        git(self.repo, self.home, "switch", "-q", "-c", "pr")
        self.script = self.runner.script

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def gs(self, *args: str):
        head = git(self.repo, self.home, "rev-parse", "HEAD")
        return self.runner.offline("--pr-head", head, *args)

    def test_docs_only_pr_posts_docs_only(self) -> None:
        commit(self.repo, self.home, msg("Plan"), {"planning-docs/b.md": "b\n"})
        self.assertEqual(self.gs("--check").returncode, 0)
        r = self.gs("--docs-only", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("context=local-gate", r.stdout)
        self.assertIn("description=docs only, no local gate", r.stdout)

    def test_code_pr_is_not_docs_only(self) -> None:
        commit(self.repo, self.home, msg("Code"), {"src/tool.py": "print(2)\n"})
        self.assertEqual(self.gs("--check").returncode, 1)
        self.assertEqual(self.gs("--docs-only", "--dry-run").returncode, 1)

    def test_rename_from_src_into_docs_rejected(self) -> None:
        git(self.repo, self.home, "mv", "src/tool.py", "planning-docs/tool.py")
        commit(self.repo, self.home, msg("Move"))
        r = self.gs("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not on the base branch's docs-only list: src/tool.py", r.stdout)

    def test_pr_widening_the_list_rejected(self) -> None:
        lst = self.repo / ".github/docs-only-paths"
        lst.write_text(lst.read_text() + "src/\n")
        commit(self.repo, self.home, msg("Widen"), {"src/tool.py": "print(3)\n"})
        r = self.gs("--docs-only", "--dry-run")
        self.assertEqual(r.returncode, 1)
        out = self.gs("--check").stdout
        self.assertIn("enforcement path: .github/docs-only-paths", out)
        self.assertIn("not on the base branch's docs-only list: src/tool.py", out)

    def test_branch_copy_of_script_is_not_used(self) -> None:
        self.script.write_text(
            self.script.read_text().replace("def docs_only(entries", "def _real(entries", 1)
            + "\n\ndef docs_only(entries, recs):\n    return []\n"
        )
        commit(self.repo, self.home, msg("Loosen gate-status"), {"src/tool.py": "print(4)\n"})
        r = self.gs("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("running the base copy", r.stderr)

    def test_binary_rejected(self) -> None:
        (self.repo / "planning-docs/pic.png").write_bytes(b"\x89PNG\x00\x01\x02")
        commit(self.repo, self.home, msg("Pic"))
        r = self.gs("--check")
        self.assertIn("binary: planning-docs/pic.png", r.stdout)

    def test_full_run_refusals(self) -> None:
        commit(self.repo, self.home, msg("Code"), {"src/tool.py": "print(5)\n"})
        self.assertEqual(self.gs("--passed", "10", "--skipped", "1", "--dry-run").returncode, 1)
        r = self.gs("--passed", "10", "--skipped", "0", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("description=10 passed, 0 skipped", r.stdout)
        (self.repo / "stray.txt").write_text("x")
        r = self.gs("--passed", "10", "--skipped", "0", "--dry-run")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not clean", r.stderr)
        (self.repo / "stray.txt").unlink()
        stale = git(self.repo, self.home, "rev-parse", "HEAD~1")
        r = self.runner.offline("--pr-head", stale, "--passed", "10", "--skipped", "0", "--dry-run")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not the PR head", r.stderr)


if __name__ == "__main__":
    unittest.main()
