"""Tests for the uv + multi-user round (operator decisions 2026-11-10).

Change A: every entry point and hook starts with a POSIX sh front that needs uv; `bin/bootstrap`
checks the computer and offers `brew install uv` only at a terminal outside Claude Code.
Change B: `scripts/setup`, the AGENTS.md People section, number placeholders, CODEOWNERS, and
rules_check flagging a deleted hook.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

from helpers import FAKE_UV, OUT, commit, env, git, init_repo, msg, write_exe
from test_apply_rules import KitCase

UV_MSG = "uv is required: brew install uv (or see https://docs.astral.sh/uv/getting-started/installation/)"
SYSTEM_DIRS = ["/usr/bin", "/bin"]
ENTRY_POINTS = [
    "bin/dev-ai-standards",
    "bin/gate-status",
    "bin/new-claude-project",
    "scripts/check",
    *[f"checks/{n}.py" for n in ("pre_commit", "rules_check", "secret_scan")],
    *[f"checks/{n}.py" for n in ("shell_lint", "state_check", "trailer_check")],
]
FRONT_END = '":\n'


def front(path: Path) -> str:
    text = path.read_text()
    return text[: text.index(FRONT_END) + len(FRONT_END)]


class Front(KitCase):
    def no_uv_env(self, extra_dirs: list[str] | None = None) -> dict[str, str]:
        dirs = [*(extra_dirs or []), *SYSTEM_DIRS]
        self.assertFalse(any((Path(d) / "uv").exists() for d in dirs), "uv on the test PATH")
        e = env(self.home)
        e["PATH"] = os.pathsep.join(dirs)
        # The front also looks in uv's usual install folders (U1-5); this machine may have one.
        e["DEV_AI_STANDARDS_NO_UV_SEARCH"] = "1"
        return e

    def test_every_entry_point_prints_the_uv_message_without_uv(self) -> None:
        e = self.no_uv_env()
        for rel in ENTRY_POINTS:
            with self.subTest(rel=rel):
                r = subprocess.run(
                    ["/bin/sh", str(OUT / rel), "--help"],
                    cwd=self.tmp,
                    env=e,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(r.returncode, 1)
                self.assertEqual(r.stderr, UV_MSG + "\n")
                self.assertEqual(r.stdout, "")

    def test_fronts_are_identical_and_ask_for_312(self) -> None:
        want = front(OUT / "bin/dev-ai-standards")
        self.assertTrue(want.startswith("#!/bin/sh\n# /// script\n"))
        self.assertIn('# requires-python = ">=3.12"\n', want)
        self.assertIn('exec uv run --script "$0" "$@"\n', want)
        for rel in [*ENTRY_POINTS, "templates/scripts/check"]:
            with self.subTest(rel=rel):
                self.assertEqual(front(OUT / rel), want)
                self.assertNotIn("from __future__", (OUT / rel).read_text())

    def test_front_runs_the_tool_through_uv(self) -> None:
        r = subprocess.run(
            ["/bin/sh", str(self.kit / "bin/dev-ai-standards"), "--help"],
            cwd=self.tmp,
            env=env(self.home),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("usage: dev-ai-standards", r.stdout)

    def test_launcher_without_uv_stops_before_anything(self) -> None:
        r = subprocess.run(
            ["/bin/sh", str(self.kit / "bin/new-claude-project"), "demo", "--local"],
            cwd=self.home,
            env=self.no_uv_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual((r.returncode, r.stderr, r.stdout), (1, UV_MSG + "\n", ""))
        self.assertEqual(list(self.home.iterdir()), [])

    def test_commit_hook_without_uv_prints_the_message(self) -> None:
        repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(repo)
        (repo / "m.txt").write_text(msg("Subject"))
        gitdir = str(Path(shutil.which("git") or "/usr/bin/git").parent)
        r = subprocess.run(
            ["/bin/sh", ".githooks/commit-msg", "m.txt"],
            cwd=repo,
            env=self.no_uv_env([gitdir] if gitdir not in SYSTEM_DIRS else []),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual((r.returncode, r.stderr), (1, UV_MSG + "\n"))
        hook = (repo / ".githooks/commit-msg").read_text()
        self.assertIn('exec sh docs/standards/checks/trailer_check.py --message-file "$1"', hook)
        settings = (repo / ".claude/settings.json").read_text()
        self.assertIn(
            '"sh \\"$CLAUDE_PROJECT_DIR\\"/docs/standards/checks/state_check.py', settings
        )
        self.assertNotIn("python3", settings)


class LegacyHooks(KitCase):
    def test_reapply_rewrites_python3_hooks_and_settings(self) -> None:
        repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(repo)
        for name in ("commit-msg", "pre-commit"):
            p = repo / ".githooks" / name
            p.write_text(p.read_text().replace("exec sh ", "exec python3 "))
        sp = repo / ".claude/settings.json"
        sp.write_text(sp.read_text().replace('"sh \\"$CLAUDE', '"python3 \\"$CLAUDE'))
        out = self.apply_ok(repo)
        self.assertIn("install .githooks/commit-msg, .githooks/pre-commit", out)
        for name in ("commit-msg", "pre-commit"):
            self.assertNotIn("python3", (repo / ".githooks" / name).read_text())
        text = sp.read_text()
        self.assertNotIn("python3", text)
        self.assertEqual(text.count("state_check.py --hook"), 2)


class Bootstrap(KitCase):
    def setUp(self) -> None:
        super().setUp()
        self.fakebin = self.tmp / "fakebin"
        self.fakebin.mkdir()
        self.logs = self.tmp / "logs"
        self.logs.mkdir()
        gitexe = shutil.which("git")
        assert gitexe
        (self.fakebin / "git").symlink_to(gitexe)
        write_exe(self.fakebin / "xcode-select", "#!/bin/sh\necho /Library/Developer/CLT\n")
        write_exe(self.fakebin / "brew", '#!/bin/sh\necho "brew $*" >> "$FAKE_LOG_DIR/brew.log"\n')

    def bootstrap(
        self, with_uv: bool = False, extra: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        dirs = [str(self.fakebin), *SYSTEM_DIRS]
        if with_uv:
            uvbin = self.tmp / "uvbin"
            uvbin.mkdir(exist_ok=True)
            write_exe(uvbin / "uv", FAKE_UV)
            dirs.insert(0, str(uvbin))
        if not with_uv:
            self.assertFalse(any((Path(d) / "uv").exists() for d in dirs), "uv on the test PATH")
        e = env(self.home)
        e.update(PATH=os.pathsep.join(dirs), FAKE_LOG_DIR=str(self.logs), **(extra or {}))
        # input= makes stdin a pipe: never a terminal.
        return subprocess.run(
            ["/bin/sh", str(OUT / "bin/bootstrap")],
            cwd=self.tmp,
            env=e,
            input="y\n",
            capture_output=True,
            text=True,
            check=False,
        )

    def test_refuses_to_install_without_a_tty(self) -> None:
        r = self.bootstrap()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"bootstrap: MISSING uv: {UV_MSG.removeprefix('uv is required: ')}", r.stdout)
        self.assertIn("not offering to install uv: not a terminal", r.stdout)
        self.assertFalse((self.logs / "brew.log").exists(), "brew was run")

    def test_refuses_under_claude_code(self) -> None:
        r = self.bootstrap(extra={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("under Claude Code (CLAUDECODE is set)", r.stdout)
        self.assertFalse((self.logs / "brew.log").exists(), "brew was run")

    def test_all_present(self) -> None:
        r = self.bootstrap(with_uv=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("bootstrap: ok      git", r.stdout)
        self.assertIn("bootstrap: ok      uv", r.stdout)
        self.assertIn("bootstrap: all present", r.stdout)

    def test_missing_command_line_tools_prints_the_command(self) -> None:
        if sys.platform != "darwin":
            self.skipTest("the Xcode check runs on macOS only")
        write_exe(self.fakebin / "xcode-select", "#!/bin/sh\nexit 2\n")
        r = self.bootstrap(with_uv=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("MISSING Xcode Command Line Tools: run xcode-select --install", r.stdout)


class Setup(KitCase):
    """scripts/setup in a fresh clone: bootstrap, then core.hooksPath only when it is safe."""

    def project(self, *flags: str) -> Path:
        src = init_repo(self.tmp / "src", self.home)
        self.apply_ok(src, *flags)
        commit(src, self.home, msg("Apply standards"))
        self.assertTrue(os.access(src / "scripts/setup", os.X_OK))
        return src

    def clone(self, src: Path, name: str = "clone") -> Path:
        dst = self.tmp / name
        git(self.tmp, self.home, "clone", "-q", str(src), str(dst))
        return dst

    def setup(self, repo: Path, with_uv: bool = True) -> subprocess.CompletedProcess[str]:
        fakebin = self.tmp / "setupbin"
        if not fakebin.exists():
            fakebin.mkdir()
            gitexe = shutil.which("git")
            assert gitexe
            (fakebin / "git").symlink_to(gitexe)
            write_exe(fakebin / "xcode-select", "#!/bin/sh\necho /Library/Developer/CLT\n")
        uvbin = self.tmp / "uvbin"
        if not uvbin.exists():
            uvbin.mkdir()
            write_exe(uvbin / "uv", FAKE_UV)
        dirs = [*([str(uvbin)] if with_uv else []), str(fakebin), *SYSTEM_DIRS]
        e = env(self.home)
        e["PATH"] = os.pathsep.join(dirs)
        return subprocess.run(
            ["/bin/sh", "scripts/setup"],
            cwd=repo,
            env=e,
            input="",
            capture_output=True,
            text=True,
            check=False,
        )

    def hooks_path(self, repo: Path) -> str:
        r = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            cwd=repo,
            env=env(self.home),
            capture_output=True,
            text=True,
            check=False,
        )
        return r.stdout.strip()

    def test_sets_hooks_path_in_a_fresh_clone(self) -> None:
        dst = self.clone(self.project())
        self.assertEqual(self.hooks_path(dst), "")
        r = self.setup(dst)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("bootstrap: all present", r.stdout)
        self.assertIn("setup: hooks: set core.hooksPath to .githooks", r.stdout)
        self.assertEqual(self.hooks_path(dst), ".githooks")
        again = self.setup(dst)
        self.assertIn("setup: hooks: already on", again.stdout)

    def test_other_hooks_path_left_alone(self) -> None:
        dst = self.clone(self.project())
        git(dst, self.home, "config", "core.hooksPath", "my-hooks")
        r = self.setup(dst)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("uses core.hooksPath 'my-hooks'; left as is", r.stdout)
        self.assertEqual(self.hooks_path(dst), "my-hooks")

    def test_own_default_hooks_left_alone(self) -> None:
        dst = self.clone(self.project())
        write_exe(dst / ".git/hooks/pre-commit", "#!/bin/sh\nexit 0\n")
        r = self.setup(dst)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("has hooks of its own: pre-commit; core.hooksPath not set", r.stdout)
        self.assertEqual(self.hooks_path(dst), "")

    def test_repo_without_kit_hooks_left_alone(self) -> None:
        src = self.project()
        git(src, self.home, "rm", "-q", "-r", ".githooks")
        commit(src, self.home, msg("Drop hooks"))
        dst = self.clone(src)
        r = self.setup(dst)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("doesn't use the kit's git hooks", r.stdout)
        self.assertEqual(self.hooks_path(dst), "")

    def test_stops_when_bootstrap_fails(self) -> None:
        dst = self.clone(self.project())
        r = self.setup(dst, with_uv=False)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("setup: stopped", r.stdout)
        self.assertEqual(self.hooks_path(dst), "")


class People(KitCase):
    def apply_env(self, target: Path, extra: dict[str, str], *flags: str):
        e = env(self.home)
        e.update(extra)
        return subprocess.run(
            [sys.executable, str(self.kit / "bin/dev-ai-standards"), "apply", *flags, str(target)],
            cwd=self.home,
            env=e,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_owner_from_env(self) -> None:
        p = init_repo(self.tmp / "p", self.home)
        r = self.apply_env(p, {"NEW_CLAUDE_PROJECT_OWNER": "alice"})
        self.assertEqual(r.returncode, 0, r.stderr)
        agents = (p / "AGENTS.md").read_text()
        self.assertIn("## People\n", agents)
        self.assertIn("- Owner: alice\n- Approvers: alice\n", agents)
        self.assertLess(agents.index("## People"), agents.index("## Project"))
        self.assertIn("\n* @alice\n", (p / ".github/CODEOWNERS").read_text())
        self.assertNotIn("not a GitHub login", r.stdout)

    def test_owner_from_git_user_name(self) -> None:
        p = init_repo(self.tmp / "p", self.home)
        git(p, self.home, "config", "user.name", "Bob Smith")
        r = self.apply_env(p, {})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("- Owner: Bob Smith\n", (p / "AGENTS.md").read_text())
        owners = (p / ".github/CODEOWNERS").read_text()
        self.assertIn("# * @<github-login>", owners)
        self.assertNotIn("\n* @", owners)
        self.assertIn("owner 'Bob Smith' comes from git config user.name", r.stdout)

    def test_owner_flag_wins(self) -> None:
        p = init_repo(self.tmp / "p", self.home)
        r = self.apply_env(p, {"NEW_CLAUDE_PROJECT_OWNER": "alice"}, "--owner", "carol")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("- Owner: carol\n", (p / "AGENTS.md").read_text())

    def test_existing_agents_md_gets_people_once(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        (p / "AGENTS.md").write_text("# AGENTS.md\n\nOurs.\n\n## Project\n\nX.\n\n## Overrides\n")
        r = self.apply_env(p, {"NEW_CLAUDE_PROJECT_OWNER": "alice"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("People section", r.stdout)
        text = (p / "AGENTS.md").read_text()
        self.assertEqual(text.count("## People"), 1)
        self.assertLess(text.index("## People"), text.index("## Project"))
        r2 = self.apply_env(p, {"NEW_CLAUDE_PROJECT_OWNER": "dave"})
        self.assertEqual((p / "AGENTS.md").read_text(), text)
        self.assertNotIn("write AGENTS.md", r2.stdout)


class Codeowners(People):
    def test_written_when_absent(self) -> None:
        p = init_repo(self.tmp / "p", self.home)
        r = self.apply_env(p, {"NEW_CLAUDE_PROJECT_OWNER": "alice"})
        self.assertIn("write .github/CODEOWNERS (from template)", r.stdout)
        text = (p / ".github/CODEOWNERS").read_text()
        self.assertIn("# Example:", text)
        self.assertNotIn("{{", text)
        self.assertFalse((p / "docs/standards/templates/CODEOWNERS").exists())

    def test_existing_left_alone(self) -> None:
        p = init_repo(self.tmp / "p", self.home)
        (p / ".github").mkdir()
        (p / ".github/CODEOWNERS").write_text("* @team\n")
        r = self.apply_env(p, {"NEW_CLAUDE_PROJECT_OWNER": "alice"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((p / ".github/CODEOWNERS").read_text(), "* @team\n")
        self.assertIn(".github/CODEOWNERS already exists; left as is", r.stdout)


class RepoChecks(KitCase):
    """rules_check: number placeholders fail on main only; deleting setup files fails."""

    def project(self) -> Path:
        repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(repo)
        commit(repo, self.home, msg("Apply standards"))
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
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

    PLACEHOLDER_FILES: ClassVar[dict[str, str]] = {
        "docs/adr/ADR-NEW-use-uv.md": "# ADR-NEW: use uv\n",
        "SPEC.md": "# Spec\n\n- OD-NEW-1: use uv (operator decision 2026-11-10).\n",
    }

    def test_placeholder_on_main_fails(self) -> None:
        repo = self.project()
        commit(repo, self.home, msg("Numbers"), self.PLACEHOLDER_FILES)
        r = self.rules(repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("in a change to main: assign numbers before merging", r.stdout)
        self.assertIn("docs/adr/ADR-NEW-use-uv.md: ADR-NEW in the file name", r.stdout)
        self.assertIn("docs/adr/ADR-NEW-use-uv.md:1: ADR-NEW in the ID line", r.stdout)
        self.assertIn("SPEC.md:3: OD-NEW-1 defined", r.stdout)

    def test_placeholder_on_branch_passes(self) -> None:
        repo = self.project()
        git(repo, self.home, "switch", "-q", "-c", "feature")
        commit(repo, self.home, msg("Numbers"), self.PLACEHOLDER_FILES)
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("placeholder", r.stdout)

    def test_quoted_placeholder_on_main_passes(self) -> None:
        repo = self.project()
        commit(repo, self.home, msg("Docs"), {"NOTES.md": "Write `OD-NEW` on a branch.\n"})
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ci_events_decide_the_branch(self) -> None:
        repo = self.project()
        git(repo, self.home, "switch", "-q", "-c", "feature")
        commit(repo, self.home, msg("Numbers"), self.PLACEHOLDER_FILES)
        push_main = {"GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/main"}
        self.assertEqual(self.rules_env(repo, push_main).returncode, 1)
        pr = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_REF": "refs/pull/1/merge"}
        self.assertEqual(self.rules_env(repo, {**pr, "GITHUB_BASE_REF": "main"}).returncode, 1)
        self.assertEqual(self.rules_env(repo, {**pr, "GITHUB_BASE_REF": "stage"}).returncode, 0)

    def test_deleted_hook_fails(self) -> None:
        repo = self.project()
        git(repo, self.home, "switch", "-q", "-c", "feature")
        git(repo, self.home, "rm", "-q", ".githooks/pre-commit")
        commit(repo, self.home, msg("Drop hook"))
        r = self.rules(repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL .githooks/pre-commit deleted", r.stdout)

    def test_emptied_setup_fails(self) -> None:
        repo = self.project()
        git(repo, self.home, "switch", "-q", "-c", "feature")
        commit(repo, self.home, msg("Empty setup"), {"scripts/setup": "\n"})
        r = self.rules(repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL scripts/setup emptied", r.stdout)
