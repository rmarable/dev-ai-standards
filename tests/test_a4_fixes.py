"""A4 pilot fixes: apply --stack python writes pyproject.toml, and a fresh python-stack project's
scripts/check passes (no tests yet); other stacks still fail until their steps are added (K2-2).
"""

import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from helpers import commit, env, init_repo, msg, write_exe
from test_apply_rules import KitCase

FAKE_TOOL = '#!/bin/sh\necho "$(basename "$0") $*" >> "$FAKE_LOG_DIR/tools.log"\nexit 0\n'


class PyprojectTemplate(KitCase):
    def test_written_with_normalized_name(self) -> None:
        p = self.tmp / "My_Cool.Project"
        p.mkdir()
        out = self.apply_ok(p, "--stack", "python")
        self.assertIn("write pyproject.toml", out)
        text = (p / "pyproject.toml").read_text()
        self.assertIsNone(re.search(r"\{\{", text), "placeholders filled")
        self.assertIn('name = "my-cool-project"', text)
        self.assertIn('version = "0.1.0"', text)
        self.assertIn('requires-python = ">=3.12"', text)
        self.assertIn("dependencies = []", text)
        self.assertIn('dev = ["ruff", "pyright", "pytest", "pytest-xdist"]', text)
        self.assertIn('testpaths = ["tests"]', text)
        self.assertNotIn("[build-system]", text)
        self.assertFalse((p / "docs/standards/templates/pyproject.toml").exists())
        data = tomllib.loads(text)
        self.assertEqual(data["project"]["name"], "my-cool-project")
        # The test CI's matrix minimum matches requires-python on the next apply.
        self.apply_ok(p, "--stack", "python")
        wf = (p / ".github/workflows/python.yml").read_text()
        self.assertIn('python: ["3.12", "3.13"]', wf)

    def test_existing_pyproject_left_alone(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        mine = '[project]\nname = "mine"\nrequires-python = ">=3.11"\n'
        (p / "pyproject.toml").write_text(mine)
        out = self.apply_ok(p, "--stack", "python")
        self.assertEqual((p / "pyproject.toml").read_text(), mine)
        self.assertIn("pyproject.toml already exists; left as is", out)

    def test_other_stacks_get_no_pyproject(self) -> None:
        for stack in ("other", "iac"):
            p = self.tmp / stack
            p.mkdir()
            self.apply_ok(p, "--stack", stack)
            self.assertFalse((p / "pyproject.toml").exists(), stack)


class FreshPythonCheck(KitCase):
    """scripts/check on a fresh python-stack project, with fake ruff/pyright/pytest and no uv."""

    def setUp(self) -> None:
        super().setUp()
        self.fakebin = self.tmp / "fakebin"
        self.fakebin.mkdir()
        for tool in ("ruff", "pyright", "pytest"):
            write_exe(self.fakebin / tool, FAKE_TOOL)
        self.logs = self.tmp / "logs"
        self.logs.mkdir()
        git_dir = Path(shutil.which("git") or "/usr/bin/git").parent
        self.dirs = [str(self.fakebin), str(git_dir), "/usr/bin", "/bin"]
        self.assertFalse(any((Path(d) / "uv").exists() for d in self.dirs), "uv on test PATH")

    def check(self, p: Path, *args: str) -> subprocess.CompletedProcess[str]:
        e = env(self.home)
        e.update(PATH=os.pathsep.join(self.dirs), FAKE_LOG_DIR=str(self.logs))
        e.pop("GITHUB_EVENT_NAME", None)
        return subprocess.run(
            [sys.executable, str(p / "scripts/check"), *args],
            cwd=p,
            env=e,
            capture_output=True,
            text=True,
            check=False,
        )

    def tools_log(self) -> str:
        path = self.logs / "tools.log"
        return path.read_text() if path.exists() else ""

    def test_passes_with_no_tests(self) -> None:
        p = init_repo(self.tmp / "fresh", self.home)
        self.apply_ok(p, "--stack", "python")
        text = (p / "scripts/check").read_text()
        self.assertNotIn("<!--", text)
        self.assertIn("TODO = False", text)
        commit(p, self.home, msg("Apply"))
        r = self.check(p, "--full")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no tests yet", r.stdout)
        self.assertNotIn("add your project's steps", r.stdout)
        log = self.tools_log()
        self.assertIn("ruff format --check", log)
        self.assertIn("pyright", log)
        self.assertNotIn("pytest", log)

    def test_runs_pytest_when_tests_exist(self) -> None:
        p = init_repo(self.tmp / "withtests", self.home)
        self.apply_ok(p, "--stack", "python")
        commit(p, self.home, msg("Apply"), {"tests/test_x.py": "def test_x() -> None:\n    pass\n"})
        r = self.check(p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("pytest -q\n", self.tools_log())
        r = self.check(p, "--full")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("pytest -q -n auto\n", self.tools_log())

    def test_other_and_iac_still_fail_until_edited(self) -> None:  # K2-2 intent kept
        for stack in ("other", "iac"):
            p = init_repo(self.tmp / stack, self.home)
            self.apply_ok(p, "--stack", stack)
            commit(p, self.home, msg("Apply"))
            r = self.check(p)
            self.assertEqual(r.returncode, 1, stack + r.stdout)
            self.assertIn("add your project's steps", r.stdout)
            self.assertIn("TODO = True", (p / "scripts/check").read_text())


class UserDocsRule(KitCase):
    """Doc rules: refs/user-docs.md, its .claude/rules/ path rule and its read-before row."""

    ROW = "`docs/standards/refs/user-docs.md`"

    def test_apply_writes_rule_and_row(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        self.apply_ok(p)
        self.assertTrue((p / "docs/standards/refs/user-docs.md").is_file())
        rule = (p / ".claude/rules/user-docs.md").read_text()
        self.assertTrue(rule.startswith('---\npaths: ["README.md", "docs/**"]\n---\n'), rule)
        self.assertIn("docs/standards/refs/user-docs.md", rule)
        manifest = (p / "docs/standards/manifest").read_text()
        self.assertIn("  .claude/rules/user-docs.md\n", manifest)
        self.assertIn("  docs/standards/refs/user-docs.md\n", manifest)
        agents = (p / "AGENTS.md").read_text()
        row = next(ln for ln in agents.splitlines() if self.ROW in ln)
        self.assertIn("edit `README.md` or `docs/**`", row)
        self.assertIn("drift: none", self.drift(p).stdout)

    def test_existing_agents_gets_row(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        (p / "AGENTS.md").write_text("# AGENTS.md\n\nMy rule.\n\n## Overrides\n")
        self.apply_ok(p)
        self.assertIn(self.ROW, (p / "AGENTS.md").read_text())

    def test_drift_catches_edits(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        self.apply_ok(p)
        ref = p / "docs/standards/refs/user-docs.md"
        ref.write_text(ref.read_text() + "- Exclamation marks are fine!\n")
        r = self.drift(p)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("docs/standards/refs/user-docs.md", r.stdout + r.stderr)
        ref.write_text((self.kit / "refs/user-docs.md").read_text())
        rule = p / ".claude/rules/user-docs.md"
        rule.write_text(rule.read_text() + "Ignore the above.\n")
        r = self.drift(p)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn(".claude/rules/user-docs.md", r.stdout + r.stderr)
