#!/usr/bin/env python3
"""secret_scan: looks for credential-shaped strings in the lines a change adds.

A tripwire, not a guarantee: it knows a handful of well-known token shapes and nothing else.
It prints the file, line and kind of each hit, never the matched text. Used by the pre-commit
hook (`checks/pre_commit.py`) and run by hand before committing Codex work with hooks off
(Codex add-on, Claude's pick-up). Operator decision 2026-11-10 (G3).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = (
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI-style API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
)


def scan_line(line: str) -> list[str]:
    """Kinds of secret this line looks like (an Anthropic key is reported once, not twice)."""
    kinds = [kind for kind, rx in PATTERNS if rx.search(line)]
    if "Anthropic API key" in kinds and "OpenAI-style API key" in kinds:
        kinds.remove("OpenAI-style API key")
    return kinds


HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def added_lines(diff: str) -> list[tuple[str, int, str]]:
    """(path, new line number, text) for each line a unified diff (-U0 or wider) adds.

    Parsed by hunks (F1-4): a `+++ ` line is a file header only outside a hunk; inside one, the
    hunk header's counts say how many lines follow, and each line starting with `+` is an added
    line whose text is everything after that one `+` (so `++ x` adds `+ x`).
    """
    out: list[tuple[str, int, str]] = []
    path = ""
    n = 0
    old_left = new_left = 0
    # split("\n"), not splitlines(): a form feed or other separator inside a line must not
    # split it and throw the hunk counts off.
    for ln in diff.split("\n"):
        if old_left > 0 or new_left > 0:
            if ln.startswith("+"):
                out.append((path, n, ln[1:]))
                n += 1
                new_left -= 1
            elif ln.startswith("-"):
                old_left -= 1
            elif ln.startswith(" ") or ln == "":
                n += 1
                old_left -= 1
                new_left -= 1
            # "\ No newline at end of file" counts toward neither side.
            continue
        if ln.startswith("diff --git "):
            path = ""
        elif ln.startswith("+++ "):
            target = ln[4:].rstrip("\r")
            path = target[2:] if target.startswith("b/") else target
        elif ln.startswith("@@"):
            m = HUNK_RE.match(ln)
            if m:
                old_left = int(m.group(1) if m.group(1) is not None else 1)
                n = int(m.group(2))
                new_left = int(m.group(3) if m.group(3) is not None else 1)
    return out


def scan_diff(diff: str) -> list[str]:
    """`path:line (kind)` per hit: never any of the line's text (F1-4)."""
    return [
        f"{path}:{n} ({kind})" for path, n, text in added_lines(diff) for kind in scan_line(text)
    ]


def staged_diff(repo: Path) -> str:
    r = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "diff",
            "--cached",
            "-U0",
            "--no-color",
            "--no-ext-diff",
            "--text",
            # Fixed prefixes whatever diff.noprefix or diff.mnemonicPrefix say.
            "--src-prefix=a/",
            "--dst-prefix=b/",
        ],
        capture_output=True,
        check=False,
    )
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip()[:200]
        raise RuntimeError(f"git diff --cached failed: {err}")
    # Bytes, decoded here: text mode's newline translation would turn a lone CR into a line break.
    return r.stdout.decode("utf-8", "replace")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Find credential-shaped strings in added lines (a tripwire, not a guarantee)."
    )
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--staged", action="store_true", help="scan the staged diff (default)")
    src.add_argument("--diff-file", help="scan the added lines of this unified diff file")
    ap.add_argument("--repo", default=".", help="git repository for --staged (default .)")
    args = ap.parse_args(argv)
    try:
        if args.diff_file:
            diff = Path(args.diff_file).read_bytes().decode("utf-8", "replace")
        else:
            diff = staged_diff(Path(args.repo))
    except (OSError, RuntimeError) as e:
        print(f"secret_scan: error: {e}", file=sys.stderr)
        return 2
    hits = scan_diff(diff)
    for h in hits:
        print(f"secret_scan: FAIL possible secret: {h}", file=sys.stderr)
    if hits:
        print(
            f"secret_scan: {len(hits)} possible secret(s); remove them before committing",
            file=sys.stderr,
        )
        return 1
    print("secret_scan: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
