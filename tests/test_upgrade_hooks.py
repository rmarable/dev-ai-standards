"""Tests for kit upgrade PRs in checks/rules_check.py and the commit-msg hook `apply` installs.

Operator-approved changes of 2026-11-10: an upgrade PR may use its own manifest only when it
changes nothing but kit text, the manifest and a strictly newer Standards line; `apply` installs
`.githooks/commit-msg` in a repo with no hooks and otherwise prints the line to add.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from helpers import CLAUDE_TRAILER, CODEX_TRAILER, apply, commit, git, init_repo, msg, run
from test_apply_rules import KitCase

HOOK_LINE = 'python3 docs/standards/checks/trailer_check.py --message-file "$1" || exit 1'


class Upgrade(KitCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(self.repo, "--high-stakes")
        commit(self.repo, self.home, msg("Apply standards"))
        git(self.repo, self.home, "switch", "-q", "-c", "kit-upgrade")

    def new_kit(self, version: str) -> None:
        """Change kit text (a kit file and the core block) and set the kit's version."""
        (self.kit / "VERSION").write_text(version + "\n")
        self.edit(self.kit / "refs" / "honesty.md", "\n", "\nAn upgraded line.\n")
        self.edit(self.kit / "core.md", "1. Don't lie.", "1. Don't lie, ever.")

    def upgrade(self, version: str) -> None:
        self.new_kit(version)
        self.apply_ok(self.repo, "--high-stakes")
        self.assertIn(f"Standards: dev-ai-standards v{version} ", (self.repo / "AGENTS.md").read_text())

    def test_upgrade_pr_passes(self) -> None:
        self.upgrade("0.2.0")
        commit(self.repo, self.home, msg("Kit v0.2.0"))
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("kit upgrade v0.1.0 -> v0.2.0: using this branch's manifest", r.stdout)
        d = self.drift(self.repo)
        self.assertEqual(d.returncode, 0, d.stdout + d.stderr)
        mf = self.tmp / "base-manifest"
        mf.write_text(git(self.repo, self.home, "show", "main:docs/standards/manifest") + "\n")
        r = self.rules(self.repo, "--manifest", str(mf), "--base", "main")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_upgrade_with_non_kit_file_fails(self) -> None:
        self.upgrade("0.2.0")
        commit(self.repo, self.home, msg("Kit v0.2.0 and code"), {"src/app.py": "print(1)\n"})
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("kit upgrade PRs may change only kit files, the manifest and the Standards line", r.stdout)
        self.assertIn("src/app.py", r.stdout)
        self.assertIn("AGENTS.md#core: block edited", r.stdout)

    def test_upgrade_with_project_text_edit_fails(self) -> None:
        self.upgrade("0.2.0")
        self.edit(self.repo / "AGENTS.md", "## Overrides\n", "## Overrides\n\n- core: sneaked in\n")
        commit(self.repo, self.home, msg("Kit v0.2.0 plus an override"))
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("AGENTS.md: text outside kit blocks changed", r.stdout)

    def test_same_or_older_version_fails(self) -> None:
        for version in ("0.1.0", "0.0.9", "0.1.0-rc.1"):
            with self.subTest(version=version):
                git(self.repo, self.home, "switch", "-q", "-C", f"kit-{version}", "main")
                self.kit_reset()
                self.upgrade(version)
                commit(self.repo, self.home, msg(f"Kit v{version}"))
                r = self.rules(self.repo)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("strictly newer version on the Standards line", r.stdout)

    def kit_reset(self) -> None:
        for rel, old, new in (
            ("refs/honesty.md", "\nAn upgraded line.\n", "\n"),
            ("core.md", "1. Don't lie, ever.", "1. Don't lie."),
        ):
            p = self.kit / rel
            p.write_text(p.read_text().replace(old, new, 1))


class Hook(KitCase):
    def hooks_path(self, repo: Path) -> str:
        return run(["git", "config", "--get", "core.hooksPath"], repo, self.home).stdout.strip()

    def test_apply_installs_hook_in_fresh_repo(self) -> None:
        repo = init_repo(self.tmp / "repo", self.home)
        out = self.apply_ok(repo, "--dry-run")
        self.assertIn("would install .githooks/commit-msg", out)
        self.assertFalse((repo / ".githooks").exists())
        self.assertEqual(self.hooks_path(repo), "")
        self.apply_ok(repo)
        hook = repo / ".githooks" / "commit-msg"
        self.assertTrue(hook.is_file())
        self.assertTrue(os.access(hook, os.X_OK))
        self.assertIn("docs/standards/checks/trailer_check.py", hook.read_text())
        self.assertEqual(self.hooks_path(repo), ".githooks")
        self.assertIn("already installed", self.apply_ok(repo))

    def test_existing_hooks_path_left_alone(self) -> None:
        repo = init_repo(self.tmp / "repo", self.home)
        git(repo, self.home, "config", "core.hooksPath", "my-hooks")
        out = self.apply_ok(repo, "--dry-run")
        self.assertIn("core.hooksPath is 'my-hooks'", out)
        self.assertIn(HOOK_LINE, out)
        out = self.apply_ok(repo)
        self.assertIn("Add this line to my-hooks/commit-msg:", out)
        self.assertIn(HOOK_LINE, out)
        self.assertEqual(self.hooks_path(repo), "my-hooks")
        self.assertFalse((repo / ".githooks").exists())
        self.assertFalse((repo / "my-hooks").exists())

    def test_existing_githooks_dir_left_alone(self) -> None:
        repo = init_repo(self.tmp / "repo", self.home)
        (repo / ".githooks").mkdir()
        (repo / ".githooks" / "pre-push").write_text("#!/bin/sh\nexit 0\n")
        out = self.apply_ok(repo)
        self.assertIn(".githooks/ exists", out)
        self.assertIn(HOOK_LINE, out)
        self.assertEqual(self.hooks_path(repo), "")
        self.assertFalse((repo / ".githooks" / "commit-msg").exists())

    def test_hook_rejects_two_trailers(self) -> None:
        repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(repo)
        commit(repo, self.home, msg("Apply standards"))
        (repo / "a.txt").write_text("a\n")
        git(repo, self.home, "add", "a.txt")
        r = run(["git", "commit", "-q", "-m", f"Two\n\n{CLAUDE_TRAILER}\n{CODEX_TRAILER}"], repo, self.home)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("trailer_check: FAIL", r.stderr)
        r = run(["git", "commit", "-q", "-m", msg("One")], repo, self.home)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_not_a_repo_installs_nothing(self) -> None:
        p = self.tmp / "plain"
        p.mkdir()
        r = apply(self.kit, p, self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("hook: not a git repository", r.stdout)
        self.assertFalse((p / ".githooks").exists())


if __name__ == "__main__":
    unittest.main()
