"""Test helpers: a throwaway kit and throwaway git repos in a temp dir.

The kit is a copy of this tree, so tests exercise the real templates and add-ons. Git runs
with no user or system config.
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
CLAUDE_TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"
CODEX_TRAILER = "Co-Authored-By: Codex <noreply@openai.com>"
ZERO = "0" * 40


# The kit's sh front runs `uv run --script FILE ARGS`. Tests put this fake `uv` first on PATH so
# hooks and tools run on the test's own Python, offline, with no uv cache in the throwaway HOME.
# It handles only that form; anything else exits 2.
UV_FRONT_ARGS = "run --script"
FAKE_UV = f"""#!/bin/sh
if [ "$1" = run ]; then
  shift
  while [ $# -gt 0 ] && [ "$1" != --script ]; do shift; done
  if [ "$1" = --script ]; then
    shift
    exec {sys.executable} "$@"
  fi
fi
echo "fake uv: unsupported: $*" >&2
exit 2
"""
_fake_uv_dir: list[Path] = []


def fake_uv_dir() -> Path:
    """A folder holding only the fake `uv` above, made once per test process."""
    if not _fake_uv_dir:
        d = Path(tempfile.mkdtemp(prefix="kit-fake-uv-"))
        write_exe(d / "uv", FAKE_UV)
        _fake_uv_dir.append(d)
    return _fake_uv_dir[0]


def env(home: Path) -> dict[str, str]:
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    e.update(
        HOME=str(home),
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.invalid",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.invalid",
    )
    e.pop("CLAUDECODE", None)
    for k in (
        "NEW_CLAUDE_PROJECT_OWNER",
        "VIRTUAL_ENV",
        "GITHUB_EVENT_NAME",
        "GITHUB_REF",
        "GITHUB_BASE_REF",
        "GITHUB_ACTIONS",
        "DEFAULT_BRANCH",
        "UV_PYTHON",
        "DEV_AI_STANDARDS_NO_UV_SEARCH",
    ):
        e.pop(k, None)
    e["PATH"] = f"{fake_uv_dir()}{os.pathsep}{e.get('PATH', '')}"
    return e


def make_kit(base: Path) -> Path:
    """A copy of this kit (without tests and drafting notes) in a temp dir."""
    kit = base / "kit"
    shutil.copytree(
        OUT, kit, ignore=shutil.ignore_patterns("tests", "_notes", "__pycache__", ".git")
    )
    return kit


def apply(kit: Path, target: Path, home: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return py(kit / "bin" / "dev-ai-standards", "apply", *flags, str(target), cwd=home, home=home)


def run(
    cmd: list[str], cwd: Path, home: Path, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=cwd, env=env(home), capture_output=True, text=True, input=stdin, check=False
    )


def py(
    script: Path, *args: str, cwd: Path, home: Path, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(script), *args], cwd, home, stdin)


def git(repo: Path, home: Path, *args: str) -> str:
    r = run(["git", *args], repo, home)
    if r.returncode != 0:
        raise AssertionError(f"git {args} failed: {r.stderr}")
    return r.stdout.strip()


def init_repo(path: Path, home: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, home, "init", "-q", "-b", "main")
    return path


def commit(
    repo: Path,
    home: Path,
    message: str,
    files: dict[str, str] | None = None,
    allow_empty: bool = False,
) -> str:
    for rel, text in (files or {}).items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(repo, home, "add", "-A")
    # --no-verify: fixtures build bad states on purpose; the hooks have their own tests.
    args = ["commit", "-q", "--no-verify", "-m", message]
    if allow_empty:
        args.append("--allow-empty")
    git(repo, home, *args)
    return git(repo, home, "rev-parse", "HEAD")


def msg(subject: str, trailer: str | None = CLAUDE_TRAILER) -> str:
    return subject + ("\n\n" + trailer if trailer else "")


# A fake `gh` for gate-status: `pr view` names base branch main; statuses and check runs are canned.
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_LOG_DIR"] + "/gh.log", "a") as f:
    f.write(" ".join(args) + "\\n")
if args[:2] == ["pr", "view"]:
    print(json.dumps({"baseRefName": "main", "headRefOid": os.environ.get("FAKE_HEAD", "")}))
elif args[:1] == ["api"] and "/statuses" in args[1]:
    print(json.dumps([{"context": "local-gate", "state": "success", "creator": {"login": "op"}}]))
elif args[:1] == ["api"] and "/check-runs" in args[1]:
    n = int(os.environ.get("FAKE_RUNS", "0"))
    print(json.dumps({"total_count": n, "check_runs": [{"name": "local-gate"}] * n}))
else:
    print("{}")
"""


def write_exe(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class GateStatusRunner:
    """Runs gate-status offline: fake `gh` on PATH, a local bare `origin` (so its fetch works)."""

    def __init__(self, tmp: Path, home: Path, repo: Path) -> None:
        self.home, self.repo = home, repo
        self.script = repo / "docs/standards/bin/gate-status"
        self.fakebin = tmp / "fakebin"
        self.fakebin.mkdir()
        write_exe(self.fakebin / "gh", FAKE_GH)
        self.logs = tmp / "logs"
        self.logs.mkdir()
        origin = tmp / "origin.git"
        git(tmp, home, "init", "-q", "--bare", "-b", "main", str(origin))
        git(repo, home, "remote", "add", "origin", str(origin))
        git(repo, home, "push", "-q", "origin", "main")

    def run(
        self, *args: str, script: Path | None = None, extra: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        e = env(self.home)
        e["PATH"] = f"{self.fakebin}{os.pathsep}{e.get('PATH', '')}"
        e["FAKE_LOG_DIR"] = str(self.logs)
        e.update(extra or {})
        return subprocess.run(
            [sys.executable, str(script or self.script), *args],
            cwd=self.repo,
            env=e,
            capture_output=True,
            text=True,
            check=False,
        )

    def offline(self, *args: str, **kw: object) -> subprocess.CompletedProcess[str]:
        return self.run("--base", "origin/main", "--repo", "o/r", *args, **kw)  # type: ignore[arg-type]
