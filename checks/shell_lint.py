#!/usr/bin/env python3
"""shell_lint: runs ShellCheck on a project's shell files. Linting only, never tests.

Shell files: `*.sh`, `*.bash`, `*.zsh`, plus files whose first line is a shell shebang
(`#!/bin/sh`, `#!/bin/bash`, `#!/usr/bin/env bash`, `#!/usr/bin/env -S bash`; `sh`, `bash`,
`dash`, `ksh` or `zsh`). `--all` lists them with git (tracked and untracked, not ignored), so a
local run sees what CI sees (F1-13); outside a git repo it walks the tree, skipping `.git/`,
`node_modules/` and `.venv/`. ShellCheck has no zsh support, so zsh files get a parse-only
`zsh -n` check instead (syntax only; operator decisions 2026-11-10, G4 and F1-5). Without
`shellcheck` it prints "shellcheck not found: skipped" and passes, unless --require (CI) makes
that a failure.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = (".git", "node_modules", ".venv")
SHEBANG_RE = re.compile(
    r"#!\s*(?:/usr/bin/env\s+(?:-S\s+)?|/(?:usr/)?(?:local/)?bin/)(sh|bash|dash|ksh|zsh)\b"
)
SUFFIXES = {".sh": "sh", ".bash": "bash", ".zsh": "zsh"}
SKIP_LINE = "shellcheck not found: skipped"


def shell_of(path: Path) -> str | None:
    """The shell a file is written for (`sh`, `bash`, `dash`, `ksh`, `zsh`), or None. A shebang
    wins over the suffix, so a `.sh` file run by zsh counts as zsh (F2-2)."""
    try:
        with path.open("rb") as f:
            first = f.readline(200)
    except OSError:
        first = b""
    m = SHEBANG_RE.match(first.decode("utf-8", "replace"))
    if m:
        return m.group(1)
    return SUFFIXES.get(path.suffix)


def is_shell(path: Path) -> bool:
    return shell_of(path) is not None


def is_zsh(path: Path) -> bool:
    return shell_of(path) == "zsh"


def candidate_files(root: Path) -> list[str]:
    """Tracked and untracked, non-ignored files (git), else a walk of the tree."""
    r = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode == 0:
        return sorted({n for n in r.stdout.split("\0") if n})
    return [p.relative_to(root).as_posix() for p in sorted(root.rglob("*"))]


def all_shell_files(root: Path) -> list[str]:
    out: list[str] = []
    for rel in candidate_files(root):
        p = root / rel
        if any(part in SKIP_DIRS for part in rel.split("/")):
            continue
        if p.is_file() and not p.is_symlink() and is_shell(p):
            out.append(rel)
    return out


def staged_shell_files(root: Path) -> list[str]:
    r = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        capture_output=True,
        text=True,
        check=False,
    )
    names = [n for n in r.stdout.split("\0") if n]
    return [
        n
        for n in names
        if not any(part in SKIP_DIRS for part in n.split("/"))
        and (root / n).is_file()
        and is_shell(root / n)
    ]


def run_shellcheck(root: Path, files: list[str], require: bool = False) -> int:
    """0 when clean or nothing to check, 1 on findings (or a required, missing shellcheck).

    ShellCheck refuses zsh (SC1071), so zsh files get a parse-only `zsh -n` check instead
    (syntax only, no lint; operator decision 2026-11-10).
    """
    zsh_files = [f for f in files if is_zsh(root / f)]
    files = [f for f in files if not is_zsh(root / f)]
    zsh_rc = run_zsh_syntax(root, zsh_files, require)
    if not files:
        if not zsh_files:
            print("shell_lint: no shell files")
        return zsh_rc
    exe = shutil.which("shellcheck")
    if exe is None:
        if require:
            print(
                "shell_lint: FAIL shellcheck not found (CI needs it; see checks/README.md)",
                file=sys.stderr,
            )
            return 1
        print(f"shell_lint: {SKIP_LINE}")
        return zsh_rc
    r = subprocess.run([exe, "--", *files], cwd=root, check=False)
    if r.returncode != 0:
        print(
            f"shell_lint: FAIL shellcheck found problems in {len(files)} file(s)", file=sys.stderr
        )
        return 1
    print(f"shell_lint: ok ({len(files)} file(s))")
    return zsh_rc


def run_zsh_syntax(root: Path, files: list[str], require: bool = False) -> int:
    """`zsh -n` on each zsh file.

    0 when clean or none; 1 on a syntax error, or when zsh is required but missing.
    """
    if not files:
        return 0
    exe = shutil.which("zsh")
    if exe is None:
        if require:
            print("shell_lint: FAIL zsh not found (CI needs it for zsh files)", file=sys.stderr)
            return 1
        for f in files:
            print(f"shell_lint: zsh not found: skipped: {f}")
        return 0
    bad = 0
    for f in files:
        r = subprocess.run([exe, "-n", "--", f], cwd=root, check=False)
        if r.returncode != 0:
            bad += 1
            print(f"shell_lint: FAIL zsh -n: syntax error in {f}", file=sys.stderr)
        else:
            print(f"shell_lint: zsh: syntax only (ShellCheck doesn't support zsh): {f}")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run ShellCheck on shell files (linting only).")
    which = ap.add_mutually_exclusive_group()
    which.add_argument("--all", action="store_true", help="every shell file in the tree (default)")
    which.add_argument("--staged", action="store_true", help="only staged shell files")
    which.add_argument("--list", action="store_true", help="print the shell files and exit")
    which.add_argument(
        "--has-zsh", action="store_true", help="exit 0 if any zsh file exists, else 1 (CI)"
    )
    ap.add_argument("--require", action="store_true", help="fail when shellcheck is missing (CI)")
    ap.add_argument("dir", nargs="?", default=".", help="project root (default .)")
    args = ap.parse_args(argv)
    root = Path(args.dir).resolve()
    files = staged_shell_files(root) if args.staged else all_shell_files(root)
    if args.list:
        for f in files:
            print(f)
        return 0
    if args.has_zsh:
        return 0 if any(is_zsh(root / f) for f in files) else 1
    return run_shellcheck(root, files, args.require)


if __name__ == "__main__":
    sys.exit(main())
