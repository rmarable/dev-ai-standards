"""Tests for bin/new-claude-project (P001 Part A, "One-command launch", "Who may run what").

Fake `gh` and `claude` executables go first on PATH; nothing calls GitHub or the network. The
kit's real bin/dev-ai-standards is used when present, else a fake (NCP_TEST_FAKE_APPLY=1 forces it).
"""

from __future__ import annotations

import os
import pty
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
SCRIPT = KIT / "bin" / "new-claude-project"
REAL_APPLY = KIT / "bin" / "dev-ai-standards"
USE_FAKE_APPLY = os.environ.get("NCP_TEST_FAKE_APPLY") == "1" or not REAL_APPLY.is_file()

FAKE_GH = """#!/bin/sh
echo "$PWD|$*" >> "$FAKE_LOG_DIR/gh.log"
case "$1 $2" in
  "auth status") exit 0 ;;
  "repo view")
    if [ -n "$FAKE_GH_EXISTS" ]; then echo '{"name":"x"}'; exit 0; fi
    echo "GraphQL: Could not resolve to a Repository with the name '$3'. (repository)" >&2
    exit 1 ;;
  "repo create") exit 0 ;;
  "api "*)
    cat >> "$FAKE_LOG_DIR/gh-api-input.log"
    echo >> "$FAKE_LOG_DIR/gh-api-input.log"
    exit 0 ;;
esac
exit 0
"""

FAKE_CLAUDE = """#!/bin/sh
echo "$PWD|$*" >> "$FAKE_LOG_DIR/claude.log"
exit 0
"""

FAKE_APPLY = """#!/bin/sh
echo "$*" >> "$FAKE_LOG_DIR/apply.log"
[ "$1" = apply ] || exit 2
for last; do :; done
mkdir -p "$last/docs/standards"
std='Standards: dev-ai-standards v0.1.0 (core; stack other)'
printf '# AGENTS.md\\n\\n%s\\n' "$std" > "$last/AGENTS.md"
printf '@AGENTS.md\\n' > "$last/CLAUDE.md"
printf 'fake\\n' > "$last/docs/standards/manifest"
"""


def write_exe(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class LauncherTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ncp-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # A copy of the kit with no .git, so the launcher never pulls the real kit.
        self.kit = self.tmp / "kit"
        shutil.copytree(
            KIT, self.kit, ignore=shutil.ignore_patterns(".git", "_notes", "__pycache__")
        )
        if not (self.kit / "VERSION").exists():
            (self.kit / "VERSION").write_text("0.1.0\n")
        self.script = self.kit / "bin" / "new-claude-project"
        self.logs = self.tmp / "logs"
        self.logs.mkdir()
        self.src = self.tmp / "src"
        self.src.mkdir()
        fakebin = self.tmp / "fakebin"
        fakebin.mkdir()
        write_exe(fakebin / "gh", FAKE_GH)
        write_exe(fakebin / "claude", FAKE_CLAUDE)
        home = self.tmp / "home"
        home.mkdir()
        gitconfig = self.tmp / "gitconfig"
        gitconfig.write_text(
            "[user]\n\tname = Test User\n\temail = test@example.invalid\n"
            "[init]\n\tdefaultBranch = main\n"
        )
        env = {
            k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "NEW_CLAUDE_PROJECT_"))
        }
        env.pop("CLAUDECODE", None)
        env.pop("DEV_AI_STANDARDS_BIN", None)
        env.update(
            {
                "PATH": f"{fakebin}{os.pathsep}{env.get('PATH', '')}",
                "HOME": str(home),
                "GIT_CONFIG_GLOBAL": str(gitconfig),
                "GIT_CONFIG_NOSYSTEM": "1",
                "NEW_CLAUDE_PROJECT_ROOT": str(self.src),
                "FAKE_LOG_DIR": str(self.logs),
            }
        )
        if USE_FAKE_APPLY:
            fake_apply = self.tmp / "fake-dev-ai-standards"
            write_exe(fake_apply, FAKE_APPLY)
            env["DEV_AI_STANDARDS_BIN"] = str(fake_apply)
        else:
            # The real apply, behind a wrapper that logs each call, so the "apply never ran"
            # checks below can fail with the real apply too (K1-13).
            wrapper = self.tmp / "logged-dev-ai-standards"
            write_exe(
                wrapper,
                '#!/bin/sh\necho "$*" >> "$FAKE_LOG_DIR/apply.log"\n'
                f'exec {sys.executable} {self.kit / "bin" / "dev-ai-standards"} "$@"\n',
            )
            env["DEV_AI_STANDARDS_BIN"] = str(wrapper)
        self.env = env
        # The kit copy tracks a local bare "upstream", so the preflight's pull needs no network.
        upstream = self.tmp / "kit-upstream.git"
        for cmd in (
            ["git", "init", "-q", "-b", "main"],
            ["git", "add", "-A"],
            ["git", "commit", "-q", "-m", "kit"],
            ["git", "init", "-q", "--bare", str(upstream)],
            ["git", "remote", "add", "origin", str(upstream)],
            ["git", "push", "-q", "-u", "origin", "main"],
        ):
            subprocess.run(cmd, cwd=self.kit, env=env, check=True, capture_output=True)

    def run_script(self, *args: str, **extra_env: str) -> subprocess.CompletedProcess[str]:
        env = dict(self.env, **extra_env)
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            env=env,
            text=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )

    def run_in_pty(self, args: list[str], answers: str, **extra_env: str) -> tuple[int, str]:
        """Run with stdin and stdout on a terminal, as a human would; answers are typed up front."""
        master, slave = pty.openpty()
        env = dict(self.env, **extra_env)
        proc = subprocess.Popen(
            [sys.executable, str(self.script), *args],
            env=env,
            stdin=slave,
            stdout=slave,
            stderr=slave,
        )
        os.close(slave)
        out: list[bytes] = []

        def drain() -> None:
            while True:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    return
                if not chunk:
                    return
                out.append(chunk)

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        os.write(master, answers.encode())
        code = proc.wait(timeout=120)
        reader.join(timeout=10)
        os.close(master)
        return code, b"".join(out).decode("utf-8", "replace")

    def log(self, name: str) -> str:
        path = self.logs / name
        return path.read_text() if path.exists() else ""

    def test_dry_run_changes_nothing(self) -> None:
        before = sorted(p.name for p in self.src.iterdir())
        for extra in (["--local"], []):
            res = self.run_script("demo", "--dry-run", *extra, CLAUDECODE="1")
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("Dry run", res.stdout)
            self.assertNotIn("Nothing was created", res.stdout + res.stderr)
        self.assertEqual(sorted(p.name for p in self.src.iterdir()), before)
        self.assertFalse((self.src / "demo").exists())
        self.assertEqual(self.log("apply.log"), "")
        self.assertEqual(self.log("claude.log"), "")
        gh_calls = [line.split("|", 1)[1] for line in self.log("gh.log").splitlines()]
        self.assertTrue(all(c.startswith(("auth status", "repo view")) for c in gh_calls), gh_calls)

    def test_local_builds_repo(self) -> None:
        res = self.run_script("demo", "--local", "--codex")
        self.assertEqual(res.returncode, 0, res.stderr + res.stdout)
        target = self.src / "demo"
        self.assertTrue((target / "AGENTS.md").is_file())
        self.assertTrue((target / "planning-docs/milestones/M1-demo.md").is_file())
        msg = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            cwd=target,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip()
        self.assertEqual(
            msg,
            "new-claude-project: initial commit\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
        )
        parents = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=target,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip()
        self.assertEqual(parents, "1")
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=target,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        ).stdout
        self.assertEqual(status, "")
        self.assertEqual(self.log("gh.log"), "")
        self.assertEqual(self.log("claude.log"), "")  # no TTY: next steps printed instead
        self.assertIn("worktree add -b codex/<topic>", res.stdout)
        self.assertIn("apply --stack other --codex", self.log("apply.log"))
        if not USE_FAKE_APPLY:
            drift = subprocess.run(
                [str(REAL_APPLY), "drift", str(target)],
                env=self.env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(drift.returncode, 0, drift.stdout + drift.stderr)

    def test_remote_refused_when_claudecode_set(self) -> None:
        for args in (["demo"], ["demo", "--public"], ["demo", "--no-pr"]):
            res = self.run_script(*args, CLAUDECODE="1")
            self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
            self.assertIn("refused", res.stderr)
        code, out = self.run_in_pty(["demo"], "\n\nn\ny\n", CLAUDECODE="1")
        self.assertEqual(code, 2, out)
        self.assertFalse((self.src / "demo").exists())
        self.assertEqual(self.log("gh.log"), "")
        self.assertEqual(self.log("apply.log"), "")

    def test_remote_refused_without_tty(self) -> None:
        res = self.run_script("demo")
        self.assertEqual(res.returncode, 2)
        self.assertFalse((self.src / "demo").exists())

    def test_existing_folder_stops(self) -> None:
        (self.src / "demo").mkdir()
        (self.src / "demo" / "keep.txt").write_text("mine\n")
        res = self.run_script("demo", "--local")
        self.assertEqual(res.returncode, 1)
        self.assertIn("already exists", res.stderr)
        self.assertEqual(sorted(p.name for p in (self.src / "demo").iterdir()), ["keep.txt"])
        self.assertEqual(self.log("apply.log"), "")

    def test_existing_remote_stops(self) -> None:
        res = self.run_script("demo", "--dry-run", CLAUDECODE="1", FAKE_GH_EXISTS="1")
        self.assertEqual(res.returncode, 1)
        self.assertIn("already exists on GitHub", res.stderr)

    def test_failed_apply_reports_and_keeps(self) -> None:
        bad = self.tmp / "bad-apply"
        write_exe(bad, "#!/bin/sh\necho boom >&2\nexit 3\n")
        res = self.run_script("demo", "--local", DEV_AI_STANDARDS_BIN=str(bad))
        self.assertEqual(res.returncode, 1)
        self.assertIn("Already exists", res.stderr)
        self.assertTrue((self.src / "demo" / ".git").is_dir())

    def test_interactive_private_skips_ruleset_and_opens_claude(self) -> None:
        code, out = self.run_in_pty(["demo"], "\n\nn\ny\n")
        self.assertEqual(code, 0, out)
        self.assertIn("repo create rmarable/demo --private --source . --push", self.log("gh.log"))
        self.assertNotIn("|api", self.log("gh.log"))
        self.assertIn("Ruleset skipped: GitHub Free", out)
        claude = self.log("claude.log")
        self.assertIn(str((self.src / "demo").resolve()), claude)
        self.assertIn("Read AGENTS.md", claude)

    def test_interactive_decline_keeps_build(self) -> None:
        code, out = self.run_in_pty(["demo", "--no-launch"], "\n\nn\n\x04")
        self.assertEqual(code, 1, out)
        self.assertIn("not confirmed", out)
        self.assertTrue((self.src / "demo" / "AGENTS.md").is_file())
        self.assertNotIn("repo create", self.log("gh.log"))

    def test_interactive_public_sets_ruleset(self) -> None:
        code, out = self.run_in_pty(["demo", "--public", "--no-launch"], "\n\nn\ndemo\ny\n")
        self.assertEqual(code, 0, out)
        self.assertIn("Secret scan: clean", out)
        self.assertIn("--public --source . --push", self.log("gh.log"))
        self.assertIn('"name": "main"', self.log("gh-api-input.log"))
        self.assertIn('"pull_request"', self.log("gh-api-input.log"))
        self.assertEqual(self.log("claude.log"), "")

    def test_public_secret_scan_stops(self) -> None:
        leaky = self.tmp / "leaky-apply"
        key = "AKIA" + "ABCDEFGHIJKLMNOP"
        write_exe(leaky, f'#!/bin/sh\nfor last; do :; done\necho "key={key}" > "$last/notes.txt"\n')
        code, out = self.run_in_pty(
            ["demo", "--public"], "\n\nn\ndemo\ny\n", DEV_AI_STANDARDS_BIN=str(leaky)
        )
        self.assertEqual(code, 1, out)
        self.assertIn("notes.txt:1 (AWS access key id)", out)
        self.assertNotIn(key, out)
        self.assertNotIn("repo create", self.log("gh.log"))

    def test_public_wrong_name_stops(self) -> None:
        code, out = self.run_in_pty(["demo", "--public"], "\n\nn\nnope\ny\n")
        self.assertEqual(code, 1, out)
        self.assertNotIn("repo create", self.log("gh.log"))


if __name__ == "__main__":
    unittest.main()
