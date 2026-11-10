#!/usr/bin/env python3
"""pre_commit: the git pre-commit hook `apply` installs (`.githooks/pre-commit` runs this file).

A convenience, not a boundary: `--no-verify` skips it and CI is the check. It takes the staged
file names but, except for the secret scan, reads their working-tree content (with `git add -p`
it checks what is on disk). It never runs tests or `scripts/check` (operator decision
2026-11-10, G3):
- python stack: `ruff format --check` and `ruff check` on staged `.py` files (`ruff` on PATH,
  else `.venv/bin/ruff`, else skipped; never `uv run`, F1-6);
- the secret scan (`secret_scan.py`) of the staged diff's added lines: a tripwire, not a guarantee;
- ShellCheck on staged shell files (`shell_lint.py`, G4; zsh files listed, not checked);
- `rules_check` only when kit files, the manifest, `AGENTS.md` or `CLAUDE.md` are staged;
- `state_check` as a warning only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import secret_scan  # noqa: E402
import shell_lint  # noqa: E402

KIT_PREFIX = "docs/standards/"
BLOCK_FILES = ("AGENTS.md", "CLAUDE.md")


def staged(root: Path) -> list[str]:
    r = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only", "-z"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [n for n in r.stdout.split("\0") if n]


def staged_existing(root: Path) -> list[str]:
    r = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [n for n in r.stdout.split("\0") if n]


def python_stack(root: Path) -> bool:
    agents = root / "AGENTS.md"
    if not agents.is_file():
        return False
    for ln in agents.read_text(errors="replace").splitlines():
        if ln.startswith("Standards: dev-ai-standards v"):
            return "stack python" in ln
    return False


def ruff_cmd(root: Path) -> list[str] | None:
    """`ruff` on PATH, else the project's `.venv/bin/ruff`, else None (skip).

    Never `uv run`: that syncs and builds the project inside a commit hook (F1-6).
    """
    exe = shutil.which("ruff")
    if exe:
        return [exe]
    venv = root / ".venv" / "bin" / "ruff"
    if venv.is_file() and os.access(venv, os.X_OK):
        return [str(venv)]
    return None


def check_ruff(root: Path, files: list[str]) -> bool:
    py = [f for f in files if f.endswith(".py")]
    if not py:
        return True
    ruff = ruff_cmd(root)
    if ruff is None:
        print("pre-commit: ruff not found: skipped")
        return True
    ok = True
    for args in (["format", "--check", "--force-exclude"], ["check", "--force-exclude"]):
        r = subprocess.run([*ruff, *args, "--", *py], cwd=root, check=False)
        if r.returncode != 0:
            print(f"pre-commit: FAIL ruff {args[0]}", file=sys.stderr)
            ok = False
    return ok


def check_secrets(root: Path) -> bool:
    try:
        hits = secret_scan.scan_diff(secret_scan.staged_diff(root))
    except RuntimeError as e:
        print(f"pre-commit: FAIL secret scan: {e}", file=sys.stderr)
        return False
    for h in hits:
        print(f"pre-commit: FAIL possible secret: {h}", file=sys.stderr)
    return not hits


def check_shell(root: Path, files: list[str]) -> bool:
    shell = [f for f in files if (root / f).is_file() and shell_lint.is_shell(root / f)]
    if not shell:
        return True
    return shell_lint.run_shellcheck(root, shell) == 0


def check_rules(root: Path, names: list[str]) -> bool:
    if not any(n.startswith(KIT_PREFIX) or n in BLOCK_FILES for n in names):
        return True
    r = subprocess.run(
        [sys.executable, str(HERE / "rules_check.py"), str(root)], cwd=root, check=False
    )
    return r.returncode == 0


def warn_state(root: Path) -> None:
    if (root / "CLAUDE-STATE.md").is_file():
        subprocess.run(
            [sys.executable, str(HERE / "state_check.py"), str(root / "CLAUDE-STATE.md")],
            cwd=root,
            check=False,
        )


def main() -> int:
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    )
    root = Path(top.stdout.strip() or ".")
    names = staged(root)
    existing = staged_existing(root)
    results = [check_secrets(root), check_shell(root, existing), check_rules(root, names)]
    if python_stack(root):
        results.append(check_ruff(root, existing))
    warn_state(root)
    if not all(results):
        print("pre-commit: failed (a convenience check; CI is the check)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
