"""Test helpers: a throwaway kit and throwaway git repos in a temp dir.

The kit is a copy of this tree, so tests exercise the real templates and add-ons. Git runs
with no user or system config.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
CLAUDE_TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"
CODEX_TRAILER = "Co-Authored-By: Codex <noreply@openai.com>"
ZERO = "0" * 40


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
    return e


def make_kit(base: Path) -> Path:
    """A copy of this kit (without tests and drafting notes) in a temp dir."""
    kit = base / "kit"
    shutil.copytree(OUT, kit, ignore=shutil.ignore_patterns("tests", "_notes", "__pycache__", ".git"))
    return kit


def apply(kit: Path, target: Path, home: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return py(kit / "bin" / "dev-ai-standards", "apply", *flags, str(target), cwd=home, home=home)


def run(cmd: list[str], cwd: Path, home: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env(home), capture_output=True, text=True, input=stdin)


def py(script: Path, *args: str, cwd: Path, home: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
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


def commit(repo: Path, home: Path, message: str, files: dict[str, str] | None = None, allow_empty: bool = False) -> str:
    for rel, text in (files or {}).items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(repo, home, "add", "-A")
    args = ["commit", "-q", "-m", message]
    if allow_empty:
        args.append("--allow-empty")
    git(repo, home, *args)
    return git(repo, home, "rev-parse", "HEAD")


def msg(subject: str, trailer: str | None = CLAUDE_TRAILER) -> str:
    return subject + ("\n\n" + trailer if trailer else "")
