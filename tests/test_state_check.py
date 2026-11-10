"""Tests for checks/state_check.py: warn-only sizes; the hook names only the edit it warns on.

P001 Verification, "state_check names only the edit it warns on".
"""

import json
import tempfile
import unittest
from pathlib import Path

from helpers import OUT, commit, git, init_repo, msg, py

SCRIPT = OUT / "checks" / "state_check.py"


def state(next_steps: int = 2, long_line: bool = False) -> str:
    lines = ["# CLAUDE-STATE.md", "", "_Last updated: 2026-11-10_", "", "## Current task", ""]
    lines.append("- task: " + ("x" * 320 if long_line else "short"))
    lines += ["", "## Next steps", ""] + [f"- step {i}" for i in range(next_steps)]
    lines += ["", "## Recent progress", "", "- done"]
    return "\n".join(lines) + "\n"


class StateCheck(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.file = self.tmp / "CLAUDE-STATE.md"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_file(self):
        return py(SCRIPT, str(self.file), cwd=self.tmp, home=self.home)

    def hook(self, payload: dict[str, object]):
        return py(
            SCRIPT,
            "--hook",
            "post-tool-use",
            cwd=self.tmp,
            home=self.home,
            stdin=json.dumps(payload),
        )

    def test_within_limits_is_silent(self) -> None:
        self.file.write_text(state())
        r = self.run_file()
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_over_limits_warns_but_passes(self) -> None:
        self.file.write_text(state(next_steps=11, long_line=True) + "y" * 9000 + "\n")
        r = self.run_file()
        self.assertEqual(r.returncode, 0)
        self.assertIn("characters, over 300", r.stdout)
        self.assertIn("'Next steps' has 11 entries, over 10", r.stdout)
        self.assertIn("over 8192", r.stdout)

    def test_hook_reports_only_the_edit(self) -> None:
        self.file.write_text(state(long_line=True))
        edit = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(self.file),
                "old_string": "- done",
                "new_string": "- done today",
            },
        }
        r = self.hook(edit)
        self.assertEqual(
            (r.returncode, r.stderr), (0, ""), "an old long line elsewhere is not this edit's"
        )
        long_new = "- done " + "z" * 310
        self.file.write_text(state(long_line=True).replace("- done", long_new))
        edit["tool_input"] = {
            "file_path": str(self.file),
            "old_string": "- done",
            "new_string": long_new,
        }
        r = self.hook(edit)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertIn("line 16 is 317 characters", r.stderr)

    def test_hook_ignores_other_files(self) -> None:
        other = self.tmp / "notes.md"
        other.write_text("x" * 400 + "\n")
        r = self.hook({"tool_name": "Write", "tool_input": {"file_path": str(other)}})
        self.assertEqual(r.returncode, 0)

    def test_finds_main_checkout_from_worktree(self) -> None:
        repo = init_repo(self.tmp / "main", self.home)
        commit(repo, self.home, msg("A"), {"a": "1"})
        (repo / "CLAUDE-STATE.md").write_text(state(next_steps=12))
        wt = self.tmp / "wt"
        git(repo, self.home, "worktree", "add", "-q", str(wt), "-b", "side")
        r = py(SCRIPT, cwd=wt, home=self.home)
        self.assertEqual(r.returncode, 0)
        self.assertIn("'Next steps' has 12 entries", r.stdout)


if __name__ == "__main__":
    unittest.main()
