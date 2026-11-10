"""Tests for the F1 review fixes (fix round 3, operator-approved 2026-11-10) and G5 (test CI).

Force pushes are in test_ci_push.py and `gate-status --no-fetch` in test_a3_fixes.py; this file
holds the rest: the renamed state template (F1-3), the secret-scan diff parser (F1-4), zsh files
(F1-5), the hook's Ruff lookup (F1-6), the state rule and upgrade rows (F1-9, F1-11), git-listed
shell files (F1-13), and the python test workflow (G5). Fake keys are built at runtime.
"""

import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import OUT, commit, env, git, init_repo, msg, py, write_exe
from test_apply_rules import KitCase
from test_hooks_lint import PreCommitBase, fakes, load, logger

SCAN = OUT / "checks" / "secret_scan.py"
SHELL_LINT = OUT / "checks" / "shell_lint.py"


class StateTemplateName(KitCase):
    """F1-3: a project's own unanchored `CLAUDE-STATE.md` ignore can't hide the kit copy."""

    def test_project_ignore_does_not_hide_kit_copy(self) -> None:
        repo = init_repo(self.tmp / "repo", self.home)
        (repo / ".gitignore").write_text("CLAUDE-STATE.md\nCLAUDE.local.md\n")
        self.apply_ok(repo)
        kit_copy = "docs/standards/templates/CLAUDE-STATE.template.md"
        self.assertTrue((repo / kit_copy).is_file())
        self.assertFalse((repo / "docs/standards/templates/CLAUDE-STATE.md").exists())
        r = subprocess.run(
            ["git", "check-ignore", "-q", kit_copy], cwd=repo, env=env(self.home), check=False
        )
        self.assertEqual(r.returncode, 1, "kit copy must not be ignored")
        self.assertTrue((repo / "CLAUDE-STATE.md").is_file(), "placeholder still written")
        git(repo, self.home, "add", "-A")
        tracked = git(repo, self.home, "ls-files").splitlines()
        self.assertIn(kit_copy, tracked)
        self.assertNotIn("CLAUDE-STATE.md", tracked)
        commit(repo, self.home, msg("Apply standards"))
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_kit_gitignore_lines_unanchored(self) -> None:
        text = (OUT / "templates/gitignore").read_text()
        for line in ("HANDOFF.md", "CLAUDE-STATE.md", "CLAUDE.local.md", "state-archive/"):
            self.assertIn(f"\n{line}\n", text)
        self.assertNotIn("/CLAUDE-STATE.md", text)


class SecretScanHunks(KitCase):
    """F1-4: hunk-aware parsing; output names file and line only."""

    def scan_staged(self, files: dict[str, str], *config: str) -> subprocess.CompletedProcess[str]:
        repo = init_repo(self.tmp / f"r{len(list(self.tmp.iterdir()))}", self.home)
        for c in config:
            k, _, v = c.partition("=")
            git(repo, self.home, "config", k, v)
        for rel, text in files.items():
            (repo / rel).write_text(text)
            git(repo, self.home, "add", rel)
        return py(SCAN, "--staged", "--repo", str(repo), cwd=repo, home=self.home)

    def test_f1_reproduction_caught_and_not_printed(self) -> None:
        aws = "AKIA" + "Q" * 16
        ant = "sk-" + "ant-" + "y" * 24
        r = self.scan_staged({"a.txt": f"++ {aws}\n", "b.txt": f"++ b/{aws}\nk={ant}\n"})
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 1, out)
        self.assertIn("a.txt:1 (AWS access key id)", out)
        self.assertIn("b.txt:1 (AWS access key id)", out)
        self.assertIn("b.txt:2 (Anthropic API key)", out)
        self.assertNotIn(aws, out)
        self.assertNotIn(ant, out)

    def test_no_output_for_any_pattern_contains_the_secret(self) -> None:
        shapes = ("v={v}", "++ {v}", "+++ b/{v}", "+++ {v}", "-- {v}", "--- a/{v}", "@@ {v}")
        for kind, value in fakes().items():
            body = "".join(s.format(v=value) + "\n" for s in shapes)
            with self.subTest(kind=kind):
                r = self.scan_staged({"f.txt": "start\n" + body})
                out = r.stdout + r.stderr
                self.assertEqual(r.returncode, 1, out)
                for n in range(2, 2 + len(shapes)):
                    self.assertIn(f"f.txt:{n} ({kind})", out)
                self.assertNotIn(value, out)
                for line in out.splitlines():
                    self.assertRegex(
                        line,
                        r"^secret_scan: (FAIL possible secret: f\.txt:\d+ \([A-Za-z -]+\)"
                        r"|\d+ possible secret\(s\); remove them before committing)$",
                    )

    def test_header_lines_only_outside_hunks(self) -> None:
        secret_scan = load("secret_scan_f1", SCAN)
        diff = (
            "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,2 +1,3 @@\n ctx\n-old\n++++ b/evil\n"
            "+\x0cform feed\n\\ No newline at end of file\n"
            "diff --git a/y b/y\n--- /dev/null\n+++ b/y\n@@ -0,0 +1 @@\n+y1\n"
        )
        self.assertEqual(
            secret_scan.added_lines(diff),
            [("x", 2, "+++ b/evil"), ("x", 3, "\x0cform feed"), ("y", 1, "y1")],
        )

    def test_noprefix_config_keeps_paths(self) -> None:
        aws = "AKIA" + "Z" * 16
        r = self.scan_staged({"c.txt": f"{aws}\n"}, "diff.noprefix=true")
        self.assertIn("c.txt:1 (AWS access key id)", r.stderr)
        r = self.scan_staged({"c.txt": f"{aws}\n"}, "diff.mnemonicPrefix=true")
        self.assertIn("c.txt:1 (AWS access key id)", r.stderr)


class ShellLintFixes(KitCase):
    """F1-5 (zsh) and F1-13 (git-listed files)."""

    def lint(self, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        e = env(self.home)
        e["PATH"] = f"{self.fakebin}{os.pathsep}{e.get('PATH', '')}"
        e["FAKE_LOG_DIR"] = str(self.logs)
        return subprocess.run(
            [sys.executable, str(SHELL_LINT), *args, str(repo)],
            cwd=repo,
            env=e,
            capture_output=True,
            text=True,
            check=False,
        )

    def setUp(self) -> None:
        super().setUp()
        self.fakebin = self.tmp / "fakebin"
        self.fakebin.mkdir()
        write_exe(self.fakebin / "shellcheck", logger("shellcheck"))
        self.logs = self.tmp / "logs"
        self.logs.mkdir()
        self.repo = init_repo(self.tmp / "repo", self.home)

    def calls(self) -> list[str]:
        p = self.logs / "calls.log"
        return p.read_text().splitlines() if p.exists() else []

    @unittest.skipUnless(shutil.which("zsh"), "zsh not installed: zsh -n checks untestable here")
    def test_zsh_listed_not_checked_bash_and_sh_checked(self) -> None:
        commit(
            self.repo,
            self.home,
            msg("Scripts"),
            {
                "z": "#!/bin/zsh\necho z\n",
                "y.zsh": "echo y\n",
                "b": "#!/usr/bin/env -S bash -e\necho b\n",
                "s.sh": "echo s\n",
                "k": "#!/bin/ksh\necho k\n",
            },
        )
        r = self.lint(self.repo, "--all")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("zsh: syntax only (ShellCheck doesn't support zsh): z", r.stdout)
        self.assertIn("zsh: syntax only (ShellCheck doesn't support zsh): y.zsh", r.stdout)
        self.assertEqual(self.calls(), ["shellcheck -- b k s.sh"])

    @unittest.skipUnless(shutil.which("zsh"), "zsh not installed: zsh -n checks untestable here")
    def test_zsh_shebang_wins_over_sh_suffix(self) -> None:  # F2-2
        commit(
            self.repo,
            self.home,
            msg("Zsh with .sh"),
            {"x.sh": "#!/bin/zsh\necho x\n", "p.sh": "echo p\n"},
        )
        r = self.lint(self.repo, "--all")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("zsh: syntax only (ShellCheck doesn't support zsh): x.sh", r.stdout)
        self.assertEqual(self.calls(), ["shellcheck -- p.sh"])

    @unittest.skipUnless(shutil.which("zsh"), "zsh not installed: zsh -n checks untestable here")
    def test_zsh_syntax_error_fails(self) -> None:  # operator decision 2026-11-10: zsh -n
        commit(self.repo, self.home, msg("Bad zsh"), {"bad.zsh": "if then fi (\n"})
        r = self.lint(self.repo, "--all")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("zsh -n: syntax error in bad.zsh", r.stderr)

    def test_has_zsh(self) -> None:
        commit(self.repo, self.home, msg("Only sh"), {"a.sh": "echo a\n"})
        self.assertEqual(self.lint(self.repo, "--has-zsh").returncode, 1)
        commit(self.repo, self.home, msg("Add zsh"), {"b.zsh": "echo b\n"})
        self.assertEqual(self.lint(self.repo, "--has-zsh").returncode, 0)

    def test_all_skips_ignored_files(self) -> None:
        commit(
            self.repo,
            self.home,
            msg("Ignore build"),
            {".gitignore": "build/\n", "t.sh": "echo t\n"},
        )
        (self.repo / "build").mkdir()
        (self.repo / "build/vendor.sh").write_text("echo v\n")
        (self.repo / "new.sh").write_text("echo n\n")
        r = self.lint(self.repo, "--list")
        self.assertEqual(r.stdout.split(), ["new.sh", "t.sh"])


class HookRuff(PreCommitBase):
    """F1-6: the hook never syncs; ruff on PATH, else .venv/bin/ruff, else a skip line."""

    def ruff_calls(self) -> list[str]:
        return [ln for ln in self.calls().splitlines() if "ruff " in ln or ln.startswith("uv")]

    def setup_repo(self) -> Path:
        repo = self.make_repo("--stack", "python")
        write_exe(self.fakebin / "uv", logger("uv"))
        self.stage(repo, {"a.py": "x = 1\n"})
        return repo

    def test_ruff_on_path(self) -> None:
        repo = self.setup_repo()
        write_exe(self.fakebin / "ruff", logger("ruff"))
        venv = repo / ".venv/bin"
        venv.mkdir(parents=True)
        write_exe(venv / "ruff", logger("venvruff"))
        r = self.hook(repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            self.ruff_calls(),
            ["ruff format --check --force-exclude -- a.py", "ruff check --force-exclude -- a.py"],
        )

    def test_venv_ruff(self) -> None:
        repo = self.setup_repo()
        venv = repo / ".venv/bin"
        venv.mkdir(parents=True)
        write_exe(venv / "ruff", logger("venvruff"))
        r = self.hook(repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            self.ruff_calls(),
            [
                "venvruff format --check --force-exclude -- a.py",
                "venvruff check --force-exclude -- a.py",
            ],
        )

    def test_no_ruff_skips_and_never_uses_uv(self) -> None:
        repo = self.setup_repo()
        r = self.hook(repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ruff not found: skipped", r.stdout)
        self.assertEqual(self.ruff_calls(), [])
        self.assertNotIn("uv ", self.calls())


class UpgradeRemovesKitRowFile(KitCase):
    """F1-11: a valid upgrade may remove a file a kit read-before row names."""

    def test_upgrade_removing_row_file_passes(self) -> None:
        repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(repo, "--high-stakes")
        commit(repo, self.home, msg("Apply standards"))
        self.assertIn("docs/standards/refs/diff-review.md", (repo / "AGENTS.md").read_text())
        git(repo, self.home, "switch", "-q", "-c", "kit-upgrade")
        (self.kit / "VERSION").write_text("0.2.0\n")
        self.edit(
            self.kit / "bin/dev-ai-standards",
            '"refs/diff-review.md", ',
            "",
        )
        (self.kit / "refs/diff-review.md").unlink()
        self.apply_ok(repo, "--high-stakes")
        self.assertFalse((repo / "docs/standards/refs/diff-review.md").exists())
        commit(repo, self.home, msg("Kit v0.2.0"))
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("file removed by this kit upgrade; drop the row next", r.stdout)
        # Outside an upgrade the missing path still fails.
        git(repo, self.home, "switch", "-q", "main")
        (repo / "docs/standards/refs/honesty.md").unlink()
        r = self.rules(repo)
        self.assertIn("read-before table path missing: docs/standards/refs/honesty.md", r.stdout)


class PythonTestCI(KitCase):
    """G5: apply --stack python writes .github/workflows/python.yml; other stacks don't."""

    def test_python_stack_installs_filled_workflow(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        (p / "pyproject.toml").write_text('[project]\nname = "p"\nrequires-python = ">=3.11"\n')
        self.apply_ok(p, "--stack", "python")
        wf = (p / ".github/workflows/python.yml").read_text()
        self.assertIsNone(re.search(r"(?<!\$)\{\{", wf), "placeholders filled")
        self.assertIn('python: ["3.11", "3.13"]', wf)
        self.assertIn("uv sync --locked", wf)
        self.assertIn("scripts/check --full", wf)

    def test_equal_versions_single_entry_and_default(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        (p / "pyproject.toml").write_text('[project]\nname = "p"\nrequires-python = ">=3.13"\n')
        self.apply_ok(p, "--stack", "python")
        self.assertIn('python: ["3.13"]\n', (p / ".github/workflows/python.yml").read_text())
        q = self.tmp / "q"
        q.mkdir()
        self.apply_ok(q, "--stack", "python")
        self.assertIn('python: ["3.12", "3.13"]', (q / ".github/workflows/python.yml").read_text())

    def test_other_stacks_do_not_install_it(self) -> None:
        for stack in ("other", "iac"):
            p = self.tmp / stack
            p.mkdir()
            self.apply_ok(p, "--stack", stack)
            self.assertFalse((p / ".github/workflows/python.yml").exists(), stack)


class WorkflowText(KitCase):
    """G5: both workflows hold their key lines (text checks; no YAML library)."""

    def check_common(self, text: str) -> None:
        self.assertNotIn("\t", text)
        self.assertRegex(text, r"(?m)^on:\n  push:")
        self.assertRegex(text, r"(?m)^  pull_request:")
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read$")
        self.assertRegex(text, r"(?m)^    runs-on: ubuntu-\d+\.\d+$")
        for line in text.splitlines():
            if line.strip().startswith("uses:"):
                self.assertRegex(line, r"uses: [\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d")
            self.assertEqual((len(line) - len(line.lstrip())) % 2, 0, line)

    def test_python_template(self) -> None:
        text = (OUT / "templates/ci/python.yml").read_text()
        self.check_common(text)
        self.assertEqual(
            text.splitlines()[0],
            "# never a required check (path-filtered); rules-check is the required one.",
        )
        for pat in ('"**/*.md"', '"docs/**"', '"planning-docs/**"'):
            self.assertEqual(text.count(pat), 2, pat)
        self.assertIn("cancel-in-progress: true", text)
        self.assertIn('python: ["{{python_min}}", "{{python_latest}}"]', text)
        self.assertIn("astral-sh/setup-uv@", text)

    def test_kit_ci(self) -> None:
        text = (OUT / ".github/workflows/kit-ci.yml").read_text()
        self.check_common(text)
        self.assertNotIn("paths-ignore", text)
        self.assertIn('python: ["3.12", "3.13"]', text)
        self.assertNotIn("3.9", text)
        self.assertNotIn("actions/setup-python@", text)
        self.assertIn("astral-sh/setup-uv@", text)
        self.assertIn("apt-get install -y -q shellcheck", text)
        self.assertIn("FAIL could not install shellcheck", text)
        self.assertIn('run: sh ./scripts/check --python "${{ matrix.python }}"', text)


class TrailerApiUrl(KitCase):
    """F1-14: a non-https GITHUB_API_URL is a one-line error, not a traceback."""

    def test_http_api_url_one_line_error(self) -> None:
        repo = init_repo(self.tmp / "r", self.home)
        commit(repo, self.home, msg("A"), {"a": "1"})
        e = env(self.home)
        e["GITHUB_API_URL"] = "http://example.invalid"
        r = subprocess.run(
            [
                sys.executable,
                str(OUT / "checks/trailer_check.py"),
                "--repo",
                str(repo),
                "--commit",
                "HEAD",
                "--github-repo",
                "o/r",
            ],
            cwd=repo,
            env=e,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 2)
        self.assertIn("trailer_check: error: GITHUB_API_URL must be https", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
