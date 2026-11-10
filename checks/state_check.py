#!/usr/bin/env python3
"""state_check: warns when the local state file passes its size limits. Warn-only.

Implements P001 Part A, "The three v1.0 checks" (3) and the state-file add-on limits: file
8 KB, line 300 characters, section caps. Never blocks; sizes only, no content judgement.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

STATE_NAME = "CLAUDE-STATE.md"
FILE_LIMIT = 8 * 1024
LINE_LIMIT = 300
SECTION_CAPS = {"Next steps": 10, "Open questions": 10, "Recent progress": 16}


def main_checkout(start: Path) -> Path | None:
    """The main checkout's root, found from any worktree with `git rev-parse --git-common-dir`."""
    r = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return None
    return Path(r.stdout.strip()).parent


def sections(lines: list[str]) -> dict[str, tuple[int, int, int]]:
    """Map '## <name>' to (first line index, last line index, count of top-level '- ' items)."""
    found: dict[str, tuple[int, int, int]] = {}
    current: str | None = None
    start = 0
    count = 0
    for i, ln in enumerate([*lines, "## <end>"]):
        if ln.startswith("## ") or i == len(lines):
            if current is not None:
                found[current] = (start, i - 1, count)
            current, start, count = ln[3:].strip(), i, 0
        elif ln.startswith("- "):
            count += 1
    return found


def warnings_for(
    text: str, only_lines: set[int] | None = None, size_matters: bool = True
) -> list[str]:
    """Size warnings; with only_lines, only those touching these 1-based line numbers."""
    out: list[str] = []
    size = len(text.encode())
    if size_matters and size > FILE_LIMIT:
        out.append(f"{STATE_NAME} is {size} bytes, over {FILE_LIMIT}")
    lines = text.splitlines()
    for n, ln in enumerate(lines, 1):
        if (only_lines is None or n in only_lines) and len(ln) > LINE_LIMIT:
            out.append(f"line {n} is {len(ln)} characters, over {LINE_LIMIT}")
    for name, (first, last, count) in sections(lines).items():
        cap = SECTION_CAPS.get(name)
        if cap is None or count <= cap:
            continue
        if only_lines is None or any(first + 1 <= n <= last + 1 for n in only_lines):
            out.append(f"section '{name}' has {count} entries, over {cap}")
    return out


def edited_lines(text: str, new_string: str) -> set[int]:
    """1-based line numbers in text covered by new_string (empty if not found)."""
    idx = text.find(new_string) if new_string else -1
    if idx < 0:
        return set()
    first = text.count("\n", 0, idx) + 1
    return set(range(first, first + max(1, new_string.count("\n") + 1)))


def from_hook(payload: dict[str, object]) -> list[str]:
    """PostToolUse: report only what the Edit or Write of the state file did."""
    tool = payload.get("tool_name")
    tin = payload.get("tool_input") or {}
    if not isinstance(tin, dict):
        return []
    path = Path(str(tin.get("file_path", "")))
    if path.name != STATE_NAME or tool not in ("Edit", "Write", "MultiEdit") or not path.is_file():
        return []
    text = path.read_text()
    if tool == "Write":
        return warnings_for(text)
    edits = tin.get("edits") if tool == "MultiEdit" else [tin]
    lines: set[int] = set()
    grew = False
    for e in edits if isinstance(edits, list) else []:
        if isinstance(e, dict):
            new, old = str(e.get("new_string", "")), str(e.get("old_string", ""))
            lines |= edited_lines(text, new)
            grew = grew or len(new) > len(old)
    return warnings_for(text, only_lines=lines, size_matters=grew)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Warn when CLAUDE-STATE.md passes its size limits (never fails)."
    )
    ap.add_argument(
        "file", nargs="?", help=f"state file (default: {STATE_NAME} in the main checkout)"
    )
    ap.add_argument(
        "--hook",
        choices=("post-tool-use", "session-start"),
        help="run as a Claude Code hook (reads the hook JSON on stdin)",
    )
    args = ap.parse_args(argv)

    if args.hook == "post-tool-use":
        try:
            payload = json.load(sys.stdin)
        except ValueError:
            return 0
        warns = from_hook(payload if isinstance(payload, dict) else {})
        for w in warns:
            print(f"state_check: warning: {w}", file=sys.stderr)
        return 2 if warns else 0

    if args.file:
        path = Path(args.file)
    else:
        root = main_checkout(Path.cwd())
        if root is None:
            print("state_check: not in a git repository; nothing checked")
            return 0
        path = root / STATE_NAME
    if not path.is_file():
        print(f"state_check: {path} not found; nothing checked")
        return 0
    for w in warnings_for(path.read_text()):
        print(f"state_check: warning: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
