"""Tests for the U1 review fixes (operator-approved 2026-11-10).

U1-1 upgrade PRs may carry the hooks and scripts/check; U1-2 the gate-status recipe uses uv run;
U1-3 placeholders fail only in changes to the default branch and only where numbers live; U1-4
People counts only from the default branch, and a People change warns; U1-5/U1-6 the sh front;
U1-8 disabled hooks; U1-11 scripts/setup's last line.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import test_a5_fixes as a5
import test_upgrade_hooks as upgrade_tests
from helpers import OUT, commit, env, git, init_repo, msg, write_exe
from test_apply_rules import KitCase


class UpgradeLaunchers(upgrade_tests.Upgrade):
    """U1-1: an upgrade may change .githooks/* and scripts/check, only with a newer version."""

    def touch_launchers(self) -> None:
        for rel in (".githooks/pre-commit", "scripts/check"):
            p = self.repo / rel
            p.write_text(p.read_text() + "# started differently by the new kit\n")

    def test_upgrade_with_hooks_and_check_passes(self) -> None:
        self.upgrade("0.2.0")
        self.touch_launchers()
        commit(self.repo, self.home, msg("Kit v0.2.0 with new launchers"))
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("kit upgrade v0.1.0 -> v0.2.0", r.stdout)

    def test_hooks_without_newer_version_fail(self) -> None:
        self.upgrade("0.1.0")
        self.touch_launchers()
        commit(self.repo, self.home, msg("Same version, new launchers"))
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("strictly newer version on the Standards line", r.stdout)

    def test_nested_githooks_path_is_not_a_launcher(self) -> None:
        self.upgrade("0.2.0")
        commit(self.repo, self.home, msg("Kit v0.2.0"), {".githooks/lib/x.sh": "#!/bin/sh\n"})
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("(also changed: .githooks/lib/x.sh)", r.stdout)


class GateStatusRecipe(KitCase):
    """U1-2: every documented way to run main's gate-status copy uses uv run, never sh."""

    DOCS = ("addons/high-stakes.md", "checks/README.md", "docs/reference.md", "README.md")
    RUN = 'uv run --no-project --python 3.12 python "$d/gate-status"'

    def test_recipes_use_uv_run(self) -> None:
        texts = {rel: (OUT / rel).read_text() for rel in self.DOCS}
        texts.update({str(p): p.read_text() for p in (OUT / "skills").rglob("*.md")})
        bad = re.compile(r"\bsh\s+\"?\$\{?(?:TMPDIR|d)\}?/gate-status")
        for rel, text in texts.items():
            with self.subTest(rel=rel):
                flat = " ".join(text.split())
                self.assertIsNone(bad.search(flat))
                self.assertNotIn("$TMPDIR/gate-status", flat)
        stakes = " ".join(texts["addons/high-stakes.md"].split())
        self.assertEqual(stakes.count(self.RUN), 2)
        self.assertIn(self.RUN, " ".join(texts["checks/README.md"].split()))


class Placeholders(KitCase):
    """U1-3: placeholders fail only in a change to the default branch, only where numbers live."""

    def project(self, branch: str = "main") -> Path:
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, self.home, "init", "-q", "-b", branch)
        self.apply_ok(repo)
        commit(repo, self.home, msg("Apply standards"))
        return repo

    def rules_env(self, repo: Path, extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
        e = env(self.home)
        e.update(extra)
        return subprocess.run(
            [sys.executable, str(self.kit / "checks/rules_check.py"), str(repo)],
            cwd=repo,
            env=e,
            capture_output=True,
            text=True,
            check=False,
        )

    NEW_ADR: ClassVar[dict[str, str]] = {
        "docs/adr/NEW-foo.md": "# ADR-NEW: Foo\n\n- Status: proposed\n"
    }

    def pr(self, base: str, default: str = "main") -> dict[str, str]:
        return {
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_REF": "refs/pull/7/merge",
            "GITHUB_BASE_REF": base,
            "DEFAULT_BRANCH": default,
        }

    def test_pr_into_default_with_new_adr_fails(self) -> None:
        repo = self.project()
        git(repo, self.home, "switch", "-q", "-c", "feature")
        commit(repo, self.home, msg("ADR"), self.NEW_ADR)
        r = self.rules_env(repo, self.pr("main"))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("in a change to main: assign numbers before merging", r.stdout)
        self.assertIn("docs/adr/NEW-foo.md: NEW in the file name", r.stdout)
        self.assertIn("docs/adr/NEW-foo.md:1: ADR-NEW in the ID line", r.stdout)

    def test_feature_branch_passes(self) -> None:
        repo = self.project()
        git(repo, self.home, "switch", "-q", "-c", "feature")
        commit(repo, self.home, msg("ADR"), self.NEW_ADR)
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        push = {"GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/feature"}
        self.assertEqual(self.rules_env(repo, {**push, "DEFAULT_BRANCH": "main"}).returncode, 0)
        self.assertEqual(self.rules_env(repo, self.pr("stage")).returncode, 0)

    def test_push_to_default_fails(self) -> None:
        repo = self.project()
        git(repo, self.home, "switch", "-q", "-c", "feature")
        commit(repo, self.home, msg("ADR"), self.NEW_ADR)
        push = {"GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/main"}
        r = self.rules_env(repo, {**push, "DEFAULT_BRANCH": "main"})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("assign numbers before merging", r.stdout)

    def test_text_that_mentions_the_convention_passes(self) -> None:
        repo = self.project()
        agents = (repo / "AGENTS.md").read_text()
        agents = agents.replace(
            "## Overrides",
            "On a branch, write ADR-NEW, OD-NEW or P-NEW-2 for numbers.\n\n## Overrides",
        )
        commit(
            repo,
            self.home,
            msg("Mentions"),
            {
                "AGENTS.md": agents,
                "CHANGELOG.md": "# Changelog\n\n- Use uv (OD-NEW-1).\n",
                "NOTES.md": "Write ``OD-NEW`` here.\n\n    - OD-NEW: indented code\n",
                "tools/pat.py": 'PAT = "OD-NEW"\n',
                "docs/adr/0002-numbers.md": "# ADR 0002: Numbers\n\nWe write ADR-NEW first.\n",
            },
        )
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.rules_env(repo, self.pr("main")).returncode, 0)

    def test_definition_lines_and_plan_names_fail(self) -> None:
        repo = self.project()
        commit(
            repo,
            self.home,
            msg("Numbers"),
            {
                "SPEC.md": "# Spec\n\n- **OD-NEW-2**: keep logs (operator decision 2026-11-10)\n",
                "planning-docs/P-NEW-auth.md": "P-NEW · draft · alice · 2026-11-10\n",
            },
        )
        r = self.rules(repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("SPEC.md:3: OD-NEW-2 defined", r.stdout)
        self.assertIn("planning-docs/P-NEW-auth.md: P-NEW in the file name", r.stdout)
        self.assertIn("planning-docs/P-NEW-auth.md:1: P-NEW in the ID line", r.stdout)

    def test_untracked_files_not_scanned(self) -> None:
        repo = self.project()
        (repo / "docs/adr/NEW-scratch.md").write_text("# ADR-NEW: scratch\n")
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_master_default_branch(self) -> None:
        repo = self.project("master")
        commit(repo, self.home, msg("ADR"), self.NEW_ADR)
        r = self.rules(repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("in a change to master: assign numbers", r.stdout)
        git(repo, self.home, "switch", "-q", "-c", "feature")
        r = self.rules_env(repo, self.pr("master", default="master"))
        self.assertEqual(r.returncode, 1, r.stdout)
        # origin/HEAD follows the source repo's HEAD, so that is master again before cloning.
        git(repo, self.home, "switch", "-q", "master")
        clone = self.tmp / "clone"
        git(self.tmp, self.home, "clone", "-q", str(repo), str(clone))
        git(clone, self.home, "switch", "-q", "-c", "main")
        r = self.rules(clone)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        git(clone, self.home, "switch", "-q", "master")
        r = self.rules(clone)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


class People(KitCase):
    """U1-4: People only from the default branch's AGENTS.md; a People change warns."""

    def project(self) -> Path:
        repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(repo, "--owner", "alice")
        commit(repo, self.home, msg("Apply standards"))
        return repo

    def add_approver(self, repo: Path, who: str) -> None:
        p = repo / "AGENTS.md"
        p.write_text(p.read_text().replace("- Approvers: alice", f"- Approvers: alice, {who}"))

    def test_branch_edit_to_people_is_not_honoured(self) -> None:
        repo = self.project()
        git(repo, self.home, "switch", "-q", "-c", "feature")
        self.add_approver(repo, "mallory")
        commit(repo, self.home, msg("Add me"))
        self.add_approver(repo, "zed")
        r = self.rules(repo, "--people")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("People from main:AGENTS.md", r.stdout)
        self.assertIn("Owner: alice\nApprovers: alice\n", r.stdout)
        self.assertNotIn("mallory", r.stdout)
        self.assertNotIn("zed", r.stdout)

    def test_pr_changing_people_warns(self) -> None:
        repo = self.project()
        git(repo, self.home, "switch", "-q", "-c", "feature")
        self.add_approver(repo, "mallory")
        commit(repo, self.home, msg("Add me"))
        e = env(self.home)
        e.update(GITHUB_ACTIONS="true", GITHUB_EVENT_NAME="pull_request", GITHUB_BASE_REF="main")
        e["DEFAULT_BRANCH"] = "main"
        r = subprocess.run(
            [sys.executable, str(self.kit / "checks/rules_check.py"), str(repo)],
            cwd=repo,
            env=e,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        want = "People changed: needs the owner's approval (merge by the owner listed on main)"
        self.assertIn(f"rules_check: WARN {want}", r.stdout)
        self.assertIn(f"::warning title=rules-check::{want}", r.stdout)

    def test_no_warning_without_people_change(self) -> None:
        repo = self.project()
        git(repo, self.home, "switch", "-q", "-c", "feature")
        commit(repo, self.home, msg("Code"), {"src/a.py": "x = 1\n"})
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("WARN", r.stdout)


class FrontUv(KitCase):
    """U1-5 and U1-6: the front finds uv in its usual folders and drops UV_PYTHON."""

    def setUp(self) -> None:
        super().setUp()
        (self.home / ".local/bin").mkdir(parents=True)

    def run_front(self, extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
        e = env(self.home)
        e["PATH"] = os.pathsep.join(a5.SYSTEM_DIRS)
        e.update(extra)
        return subprocess.run(
            ["/bin/sh", str(self.kit / "checks/state_check.py"), "--help"],
            cwd=self.tmp,
            env=e,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_uv_found_in_home_local_bin_without_path(self) -> None:
        write_exe(
            self.home / ".local/bin/uv",
            '#!/bin/sh\necho "home uv: UV_PYTHON=[${UV_PYTHON-unset}] $1 $2"\n',
        )
        r = self.run_front({"UV_PYTHON": "3.9"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "home uv: UV_PYTHON=[unset] run --script\n")

    def test_search_can_be_turned_off(self) -> None:
        write_exe(self.home / ".local/bin/uv", "#!/bin/sh\necho found\n")
        r = self.run_front({"DEV_AI_STANDARDS_NO_UV_SEARCH": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("uv is required", r.stderr)


class DisabledHooks(KitCase):
    """U1-8: a hook or scripts/setup that loses its executable bit or its kit call fails."""

    def project(self) -> Path:
        repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(repo)
        commit(repo, self.home, msg("Apply standards"))
        git(repo, self.home, "switch", "-q", "-c", "feature")
        return repo

    def test_chmod_minus_x_fails(self) -> None:
        repo = self.project()
        (repo / ".githooks/pre-commit").chmod(0o644)
        commit(repo, self.home, msg("Quiet hook"))
        r = self.rules(repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL .githooks/pre-commit is no longer executable", r.stdout)

    def test_exit_0_body_fails(self) -> None:
        repo = self.project()
        commit(repo, self.home, msg("No-op hook"), {".githooks/commit-msg": "#!/bin/sh\nexit 0\n"})
        r = self.rules(repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL .githooks/commit-msg no longer calls docs/standards/checks/", r.stdout)


class SetupEnding(a5.Setup):
    """U1-11: scripts/setup says plainly when it left the hooks off."""

    def test_own_hooks_end_with_not_on(self) -> None:
        dst = self.clone(self.project())
        write_exe(dst / ".git/hooks/pre-push", "#!/bin/sh\nexit 0\n")
        r = self.setup(dst)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("from running: pre-push)", r.stdout)
        self.assertTrue(r.stdout.endswith("setup: done, git hooks NOT on (see above)\n"))

    def test_other_hooks_path_ends_with_not_on(self) -> None:
        dst = self.clone(self.project())
        git(dst, self.home, "config", "core.hooksPath", "my-hooks")
        r = self.setup(dst)
        self.assertTrue(r.stdout.endswith("setup: done, git hooks NOT on (see above)\n"))

    def test_hooks_on_ends_with_done(self) -> None:
        r = self.setup(self.clone(self.project()))
        self.assertTrue(r.stdout.endswith("setup: done\n"), r.stdout)
