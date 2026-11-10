"""Tests for G1 (gitignore merge), G2 (Ruff template), G3 (pre-commit hook, secret scan) and G4
(ShellCheck), operator decisions 2026-11-10, plus the kit's scripts/check file list (K1-14).

Secret fixtures are built at runtime from obviously fake parts, so no key-shaped literal sits in
the repo. The hook runs with a PATH holding only fakes, git, sh, a logging python3 and a logging
fake uv that runs the sh front's `uv run --script` on the test's Python.
"""

import importlib.machinery
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from helpers import FAKE_UV, OUT, commit, env, git, init_repo, msg, py
from test_apply_rules import KitCase

SCAN = OUT / "checks" / "secret_scan.py"


def load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def fakes() -> dict[str, str]:
    """One obviously fake value per pattern kind, assembled at runtime."""
    return {
        "AWS access key id": "AKIA" + "X" * 16,
        "private key block": "-----BEGIN " + "RSA PRIVATE" + " KEY-----",
        "GitHub token": "ghp" + "_" + "x" * 36,
        "Anthropic API key": "sk-" + "ant-" + "x" * 24,
        "OpenAI-style API key": "sk-" + "x" * 40,
        "Slack token": "xox" + "b-" + "0" * 12,
    }


def write_exe(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def logger(name: str) -> str:
    return f'#!/bin/sh\necho "{name} $*" >> "$FAKE_LOG_DIR/calls.log"\nexit 0\n'


class SecretScan(KitCase):
    def test_each_pattern_caught(self) -> None:
        mod = load("secret_scan_t", SCAN)
        for kind, value in fakes().items():
            with self.subTest(kind=kind):
                self.assertEqual(mod.scan_line(f"token = '{value}'"), [kind])

    def test_output_never_holds_secret_and_clean_passes(self) -> None:
        values = fakes()
        diff = "--- a/x\n+++ b/conf.txt\n@@ -0,0 +1,7 @@\n+fine\n" + "".join(
            f"+v={v}\n" for v in values.values()
        )
        f = self.tmp / "d.diff"
        f.write_text(diff)
        r = py(SCAN, "--diff-file", str(f), cwd=self.tmp, home=self.home)
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("conf.txt:2 (AWS access key id)", out)
        self.assertIn("conf.txt:7 (Slack token)", out)
        for v in values.values():
            self.assertNotIn(v, out)
        f.write_text("--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n+nothing to see\n")
        self.assertEqual(
            py(SCAN, "--diff-file", str(f), cwd=self.tmp, home=self.home).returncode, 0
        )


class PreCommitBase(KitCase):
    """Helpers for hook tests (no tests of its own, so other files can subclass it)."""

    def make_repo(self, *flags: str) -> Path:
        repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(repo, *flags)
        commit(repo, self.home, msg("Apply standards"))
        self.fakebin = self.tmp / "fakebin"
        self.fakebin.mkdir()
        gitexe = shutil.which("git")
        assert gitexe
        (self.fakebin / "git").symlink_to(gitexe)
        (self.fakebin / "sh").symlink_to("/bin/sh")
        write_exe(
            self.fakebin / "uv",
            FAKE_UV.replace(
                "#!/bin/sh\n", '#!/bin/sh\necho "uv $*" >> "$FAKE_LOG_DIR/calls.log"\n', 1
            ),
        )
        write_exe(
            self.fakebin / "python3",
            f'#!/bin/sh\necho "python3 $*" >> "$FAKE_LOG_DIR/calls.log"\nexec {sys.executable}'
            ' "$@"\n',
        )
        self.logs = self.tmp / "logs"
        self.logs.mkdir()
        return repo

    def env(self) -> dict[str, str]:
        e = env(self.home)
        e["PATH"] = str(self.fakebin)
        e["FAKE_LOG_DIR"] = str(self.logs)
        return e

    def hook(self, repo: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(repo / "docs/standards/checks/pre_commit.py")],
            cwd=repo,
            env=self.env(),
            capture_output=True,
            text=True,
            check=False,
        )

    def calls(self) -> str:
        p = self.logs / "calls.log"
        return p.read_text() if p.exists() else ""

    def stage(self, repo: Path, files: dict[str, str]) -> None:
        for rel, text in files.items():
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
            git(repo, self.home, "add", rel)


class PreCommit(PreCommitBase):
    def test_installed_alongside_commit_msg(self) -> None:
        repo = self.make_repo()
        hook = repo / ".githooks/pre-commit"
        self.assertTrue(os.access(hook, os.X_OK))
        self.assertIn("docs/standards/checks/pre_commit.py", hook.read_text())

    def test_not_installed_when_project_has_hooks(self) -> None:
        repo = init_repo(self.tmp / "repo", self.home)
        own = repo / ".git/hooks/pre-commit"
        write_exe(own, "#!/bin/sh\nexit 0\n")
        out = self.apply_ok(repo)
        self.assertIn(".git/hooks/ has hooks (pre-commit)", out)
        self.assertIn(
            "to .git/hooks/pre-commit: sh docs/standards/checks/pre_commit.py || exit 1", out
        )
        self.assertFalse((repo / ".githooks").exists())
        self.assertEqual(own.read_text(), "#!/bin/sh\nexit 0\n")

    def test_rules_check_only_for_kit_paths(self) -> None:
        repo = self.make_repo()
        self.stage(repo, {"notes.md": "x\n"})
        r = self.hook(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("rules_check", r.stdout + self.calls())
        self.stage(
            repo,
            {
                "AGENTS.md": (repo / "AGENTS.md")
                .read_text()
                .replace("## Overrides", "More project text.\n\n## Overrides")
            },
        )
        r = self.hook(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("rules_check: ok", r.stdout)

    def test_staged_secret_fails_without_echoing_it(self) -> None:
        repo = self.make_repo()
        key = fakes()["AWS access key id"]
        self.stage(repo, {"conf.txt": f"ok\nkey={key}\n"})
        r = self.hook(repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("conf.txt:2 (AWS access key id)", r.stderr)
        self.assertNotIn(key, r.stdout + r.stderr)

    def test_ruff_missing_prints_skip_and_fake_ruff_gets_staged_files_only(self) -> None:
        repo = self.make_repo("--stack", "python")
        (repo / "unstaged.py").write_text("x=1\n")
        self.stage(repo, {"a.py": "x = 1\n", "b.md": "b\n"})
        r = self.hook(repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ruff not found: skipped", r.stdout)
        write_exe(self.fakebin / "ruff", logger("ruff"))
        r = self.hook(repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = [ln for ln in self.calls().splitlines() if ln.startswith("ruff ")]
        self.assertEqual(
            lines,
            ["ruff format --check --force-exclude -- a.py", "ruff check --force-exclude -- a.py"],
        )

    def test_shellcheck_staged_shell_files_only(self) -> None:
        repo = self.make_repo()
        commit(repo, self.home, msg("old script"), {"old.sh": "#!/bin/sh\necho old\n"})
        (repo / "untracked.sh").write_text("#!/bin/sh\necho u\n")
        self.stage(
            repo,
            {
                "a.sh": "echo a\n",
                "tool": "#!/usr/bin/env bash\necho t\n",
                "py": "#!/usr/bin/env python3\n",
            },
        )
        r = self.hook(repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("shellcheck not found: skipped", r.stdout)
        write_exe(self.fakebin / "shellcheck", logger("shellcheck"))
        r = self.hook(repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = [ln for ln in self.calls().splitlines() if ln.startswith("shellcheck ")]
        self.assertEqual(lines, ["shellcheck -- a.sh tool"])

    def test_hook_never_runs_tests_or_scripts_check(self) -> None:
        repo = self.make_repo("--stack", "python")
        marker = self.tmp / "marker"
        write_exe(repo / "scripts/check", f"#!/bin/sh\ntouch {marker}-check\n")
        (repo / "tests").mkdir()
        (repo / "tests/test_marker.py").write_text(
            f"open({str(marker) + '-unittest'!r}, 'w').close()\n"
        )
        for name in ("pytest", "uv", "ruff", "shellcheck"):
            write_exe(self.fakebin / name, logger(name))
        self.stage(
            repo,
            {
                "scripts/check": (repo / "scripts/check").read_text(),
                "tests/test_marker.py": "x = 1\n",
                "AGENTS.md": (repo / "AGENTS.md")
                .read_text()
                .replace("## Overrides", "More.\n\n## Overrides"),
                "s.sh": "echo s\n",
            },
        )
        r = subprocess.run(
            ["git", "commit", "-q", "-m", msg("Change")],
            cwd=repo,
            env=self.env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.calls()
        self.assertIn("uv run --script docs/standards/checks/pre_commit.py", calls)
        self.assertNotIn("unittest", calls)
        self.assertNotIn("pytest", calls)
        self.assertFalse(Path(f"{marker}-check").exists())
        self.assertFalse(Path(f"{marker}-unittest").exists())

    def test_state_check_warns_only(self) -> None:
        repo = self.make_repo()
        (repo / "CLAUDE-STATE.md").write_text("x" * 9000 + "\n")
        self.stage(repo, {"n.md": "n\n"})
        r = self.hook(repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("state_check: warning", r.stdout)


class ShellLint(KitCase):
    def test_shebang_detection(self) -> None:
        mod = load("shell_lint_t", OUT / "checks" / "shell_lint.py")
        cases = {
            "tool": ("#!/usr/bin/env bash\necho\n", True),
            "t2": ("#!/bin/bash\n", True),
            "t3": ("#!/bin/sh\n", True),
            "t4": ("#!/usr/bin/env zsh\n", True),
            "x.sh": ("echo\n", True),
            "p": ("#!/usr/bin/env python3\n", False),
            "plain": ("bash is nice\n", False),
        }
        for name, (text, want) in cases.items():
            (self.tmp / name).write_text(text)
            with self.subTest(name=name):
                self.assertEqual(mod.is_shell(self.tmp / name), want)
        for d in (".venv", "node_modules", ".git"):
            (self.tmp / d).mkdir()
            (self.tmp / d / "in.sh").write_text("echo\n")
        found = mod.all_shell_files(self.tmp)
        self.assertIn("tool", found)
        self.assertFalse(any(f.split("/")[0] in (".venv", "node_modules", ".git") for f in found))

    def test_codex_hook_is_a_template_file(self) -> None:
        skill = (OUT / "skills/claude-codex-integration/SKILL.md").read_text()
        self.assertNotIn("set -eu", skill)
        self.assertIn("templates/hooks/codex-handoffs.sh", skill)
        tmpl = OUT / "templates/hooks/codex-handoffs.sh"
        self.assertTrue(os.access(tmpl, os.X_OK))
        sc = shutil.which("shellcheck") or (
            "/opt/homebrew/bin/shellcheck"
            if Path("/opt/homebrew/bin/shellcheck").is_file()
            else None
        )
        cmd = [sc, str(tmpl)] if sc else ["sh", "-n", str(tmpl)]
        self.assertEqual(subprocess.run(cmd, capture_output=True, check=False).returncode, 0)


class Gitignore(KitCase):
    def test_existing_lines_and_order_kept_then_nothing_added(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        mine = "build/\n# mine\n.env\nnode_modules/\n"
        (p / ".gitignore").write_text(mine)
        dry = self.apply_ok(p, "--dry-run")
        self.assertIn(".gitignore: lines added: HANDOFF.md", dry)
        self.assertEqual((p / ".gitignore").read_text(), mine)
        self.apply_ok(p)
        text = (p / ".gitignore").read_text()
        self.assertTrue(text.startswith(mine))
        added = text[len(mine) :].splitlines()
        self.assertEqual(added[:2], ["", "# dev-ai-standards"])
        self.assertNotIn(".env", added, "already present: not duplicated")
        for line in ("CLAUDE-STATE.md", ".env.*", "!.env.example", "*.pem", "*.key", ".DS_Store"):
            self.assertIn(line, added)
        self.assertEqual(text.count("# dev-ai-standards"), 1)
        out = self.apply_ok(p)
        self.assertNotIn("write .gitignore", out)

    def test_python_stack_lines(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        (p / ".gitignore").write_text("mine/\n")
        self.apply_ok(p, "--stack", "python")
        text = (p / ".gitignore").read_text()
        for line in (
            "__pycache__/",
            ".venv/",
            ".pytest_cache/",
            ".ruff_cache/",
            ".coverage",
            "htmlcov/",
            "dist/",
            "build/",
            "*.egg-info/",
        ):
            self.assertIn(f"\n{line}\n", text)
        self.assertNotIn("cdk.out/", text)
        q = self.tmp / "q"
        q.mkdir()
        self.apply_ok(q, "--stack", "iac")
        self.assertIn("\n.terraform/\n", (q / ".gitignore").read_text())


class RuffTemplate(KitCase):
    def test_written_with_target_from_pyproject(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        (p / "pyproject.toml").write_text('[project]\nname = "x"\nrequires-python = ">=3.11.2"\n')
        self.apply_ok(p, "--stack", "python")
        text = (p / "ruff.toml").read_text()
        self.assertIn('target-version = "py311"', text)
        self.assertIn("line-length = 100", text)
        self.assertIn('ignore = ["PLR2004"]', text)
        self.assertFalse((p / "docs/standards/templates/ruff.toml").exists())
        self.assertEqual(self.drift(p).returncode, 0)
        q = self.tmp / "q"
        q.mkdir()
        self.apply_ok(q, "--stack", "python")
        self.assertIn('target-version = "py312"', (q / "ruff.toml").read_text())
        o = self.tmp / "o"
        o.mkdir()
        self.apply_ok(o)
        self.assertFalse((o / "ruff.toml").exists())

    def test_existing_settings_left_alone(self) -> None:
        for name, files in (
            ("pp", {"pyproject.toml": "[tool.ruff]\nline-length = 88\n"}),
            ("dot", {".ruff.toml": "line-length = 88\n"}),
            ("plain", {"ruff.toml": "line-length = 88\n"}),
        ):
            with self.subTest(name=name):
                p = self.tmp / name
                p.mkdir()
                for rel, text in files.items():
                    (p / rel).write_text(text)
                out = self.apply_ok(p, "--stack", "python")
                self.assertIn("Ruff settings already in", out)
                self.assertNotIn("write ruff.toml", out)
                if name != "plain":
                    self.assertFalse((p / "ruff.toml").exists())
                else:
                    self.assertEqual((p / "ruff.toml").read_text(), "line-length = 88\n")


class KitCheckScript(KitCase):
    def test_ruff_files_include_bin_tools_and_skip_templates(self) -> None:
        mod = load("kit_check_t", OUT / "scripts" / "check")
        files = mod.ruff_files()
        for rel in (
            "bin/dev-ai-standards",
            "bin/gate-status",
            "bin/new-claude-project",
            "scripts/check",
            "checks/rules_check.py",
            "tests/helpers.py",
        ):
            self.assertIn(rel, files)
        self.assertFalse(any(f.startswith("templates/") for f in files))
        self.assertIn("bin/bootstrap", mod.SCRIPTS)
        self.assertNotIn("bin/bootstrap", files)
        self.assertEqual(mod.DEFAULT_PYTHON, "3.12")
        self.assertEqual(mod.FULL_PYTHONS, ("3.12", "3.13"))
        self.assertEqual(mod.pythons(None, False), ["3.12"])
        self.assertEqual(mod.pythons(None, True), ["3.12", "3.13"])
        self.assertEqual(mod.pythons(["3.13"], False), ["3.13"])
