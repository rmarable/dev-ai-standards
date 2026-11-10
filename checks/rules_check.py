#!/usr/bin/env python3
"""rules_check: checks a project's agent rule files against the dev-ai-standards kit.

Implements P001 Part A, "The three v1.0 checks" (2) and "Kit-owned and project-owned text".
Also the shared helpers (blocks, hashing, manifest) that `bin/dev-ai-standards` imports.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

BLOCK_NAMES = (
    "core",
    "high-stakes",
    "codex",
    "state-file",
    "planning",
    "multi-session",
    "python",
    "iac",
    "other",
)
MANIFEST_PATH = "docs/standards/manifest"
STANDARDS_DIR = "docs/standards"
DEFAULT_BUDGET = 24 * 1024
BASE_CANDIDATES = ("origin/main", "main")

BLOCK_RE = re.compile(r"<!-- dev-ai-standards:(begin|end) ([a-z-]+) -->")


class CheckError(Exception):
    """A problem that stops a check with a one-line reason."""


def begin_marker(name: str) -> str:
    return f"<!-- dev-ai-standards:begin {name} -->"


def end_marker(name: str) -> str:
    return f"<!-- dev-ai-standards:end {name} -->"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_blocks(text: str) -> list[tuple[str, int, int, int, int]]:
    """Return (name, begin_start, content_start, content_end, end_end) for each kit block.

    Content is the exact text between the two markers (markers excluded). Raises
    CheckError on unknown names, nesting, duplicates or unmatched markers.
    """
    blocks: list[tuple[str, int, int, int, int]] = []
    seen: set[str] = set()
    open_name: str | None = None
    open_start = content_start = 0
    for m in BLOCK_RE.finditer(text):
        kind, name = m.group(1), m.group(2)
        if name not in BLOCK_NAMES:
            raise CheckError(f"unknown kit block name '{name}'")
        if kind == "begin":
            if open_name is not None:
                raise CheckError(f"block '{name}' begins inside block '{open_name}'")
            if name in seen:
                raise CheckError(f"block '{name}' appears twice")
            open_name, open_start, content_start = name, m.start(), m.end()
        else:
            if open_name != name:
                raise CheckError(f"end marker for '{name}' without its begin marker")
            blocks.append((name, open_start, content_start, m.start(), m.end()))
            seen.add(name)
            open_name = None
    if open_name is not None:
        raise CheckError(f"block '{open_name}' has no end marker")
    return blocks


def block_contents(text: str) -> dict[str, str]:
    return {name: text[cs:ce] for name, _, cs, ce, _ in parse_blocks(text)}


def parse_manifest(text: str) -> dict[str, str]:
    """Map path (or AGENTS.md#block) to sha256 hex."""
    entries: dict[str, str] = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        m = re.fullmatch(r"([0-9a-f]{64})  (\S.*)", line)
        if not m:
            raise CheckError(f"manifest line {n} is malformed")
        entries[m.group(2)] = m.group(1)
    return entries


def format_manifest(entries: dict[str, str]) -> str:
    return "".join(f"{entries[k]}  {k}\n" for k in sorted(entries))


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=check
    )


def is_git_repo(root: Path) -> bool:
    r = git(root, "rev-parse", "--is-inside-work-tree", check=False)
    return r.returncode == 0 and r.stdout.strip() == "true"


def ref_exists(root: Path, ref: str) -> bool:
    return git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).returncode == 0


def show_file(root: Path, ref: str, path: str) -> str | None:
    r = git(root, "show", f"{ref}:{path}", check=False)
    return r.stdout if r.returncode == 0 else None


def load_manifest(
    root: Path, base: str | None = None, manifest_file: str | None = None
) -> tuple[dict[str, str], str]:
    """Return (manifest entries, where it came from).

    The base branch's copy wins, so a branch's own manifest edit changes nothing. With no
    base branch at all (not a repo, or no main yet), or a base that has no manifest yet
    (first adoption), the working copy is used and the source says so.
    """
    if manifest_file:
        return parse_manifest(Path(manifest_file).read_text()), manifest_file
    if is_git_repo(root):
        refs = [base] if base else [r for r in BASE_CANDIDATES if ref_exists(root, r)]
        if base and not ref_exists(root, base):
            raise CheckError(f"base ref '{base}' not found")
        for ref in refs:
            text = show_file(root, ref, MANIFEST_PATH)
            if text is not None:
                return parse_manifest(text), f"{ref}:{MANIFEST_PATH}"
        if refs:
            source_note = f"working copy ({refs[0]} has no manifest yet: first adoption)"
        else:
            source_note = "working copy (no base branch)"
    else:
        source_note = "working copy (not a git repo)"
    path = root / MANIFEST_PATH
    if not path.is_file():
        raise CheckError(f"no {MANIFEST_PATH}; run 'dev-ai-standards apply'")
    return parse_manifest(path.read_text()), source_note


BLOCK_FILES = ("AGENTS.md", "CLAUDE.md")


def drift_findings(root: Path, manifest: dict[str, str]) -> list[str]:
    """Compare kit files and the kit blocks in AGENTS.md and CLAUDE.md with the manifest."""
    findings: list[str] = []
    blocks: dict[str, str] = {}
    for fname in BLOCK_FILES:
        path = root / fname
        if not path.is_file():
            continue
        try:
            for name, body in block_contents(path.read_text()).items():
                blocks[f"{fname}#{name}"] = body
        except CheckError as e:
            findings.append(f"{fname}: {e}")
    for key, want in sorted(manifest.items()):
        if "#" in key:
            if key not in blocks:
                findings.append(f"{key}: block missing")
            elif sha256_bytes(blocks[key].encode()) != want:
                findings.append(f"{key}: block edited (kit text is never edited in a project)")
        else:
            p = root / key
            if not p.is_file():
                findings.append(f"{key}: kit file missing")
            elif sha256_bytes(p.read_bytes()) != want:
                findings.append(f"{key}: kit file edited")
    for key in sorted(blocks):
        if key not in manifest:
            findings.append(f"{key}: block not in the manifest")
    std = root / STANDARDS_DIR
    if std.is_dir():
        for p in sorted(std.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                rel = p.relative_to(root).as_posix()
                if rel != MANIFEST_PATH and rel not in manifest:
                    findings.append(f"{rel}: file under {STANDARDS_DIR}/ not in the manifest")
    return findings


def overrides(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Return (override lines as (block, text), problems) from the one '## Overrides' section."""
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.rstrip() == "## Overrides"]
    problems: list[str] = []
    found: list[tuple[str, str]] = []
    if len(starts) > 1:
        problems.append(f"{len(starts)} '## Overrides' sections; there must be one")
    for start in starts[:1]:
        body: list[str] = []
        for ln in lines[start + 1 :]:
            if ln.startswith("# ") or ln.startswith("## "):
                break
            body.append(ln)
        uncommented = re.sub(r"<!--.*?-->", "", "\n".join(body), flags=re.DOTALL)
        for ln in uncommented.splitlines():
            if not ln.strip():
                continue
            m = re.fullmatch(r"- ([a-z-]+): (\S.*)", ln.rstrip())
            if not m:
                problems.append(f"malformed override line: '{ln.strip()[:80]}'")
            elif m.group(1) not in BLOCK_NAMES:
                problems.append(f"override names unknown block '{m.group(1)}'")
            else:
                found.append((m.group(1), m.group(2)))
    return found, problems


PATHLIKE_RE = re.compile(r"`([^`\s]+)`")


def read_before_paths(text: str) -> list[str]:
    """Backticked paths in the 'Read' column of every read-before table in AGENTS.md."""
    paths: list[str] = []
    col: int | None = None
    in_table = False
    for ln in text.splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            col, in_table = None, False
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not in_table:
            in_table = True
            lowered = [c.lower() for c in cells]
            if "read" in lowered:
                col = lowered.index("read")
            continue
        if col is None:
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if col < len(cells):
            for token in PATHLIKE_RE.findall(cells[col]):
                token = token.split("#", 1)[0].removeprefix("./")
                if "://" in token or "*" in token or not token:
                    continue
                if "/" in token or re.search(r"\.[A-Za-z0-9]+$", token):
                    paths.append(token)
    return paths


def has_import(claude_md: str) -> bool:
    return any(ln.strip() == "@AGENTS.md" for ln in claude_md.splitlines())


def run_checks(
    root: Path, budget: int, base: str | None, manifest_file: str | None
) -> tuple[list[str], list[str]]:
    """Return (failures, info lines)."""
    failures: list[str] = []
    info: list[str] = []
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    if not claude.is_file():
        failures.append("CLAUDE.md missing")
    elif not has_import(claude.read_text()):
        failures.append("CLAUDE.md does not import AGENTS.md (no '@AGENTS.md' line)")
    if not agents.is_file():
        failures.append("AGENTS.md missing")
        return failures, info
    text = agents.read_text()
    size = len(agents.read_bytes())
    if size > budget:
        failures.append(f"AGENTS.md is {size} bytes, over the {budget}-byte budget")
    else:
        info.append(f"AGENTS.md {size} of {budget} bytes")
    for p in read_before_paths(text):
        if not (root / p).exists():
            failures.append(f"read-before table path missing: {p}")
    try:
        manifest, source = load_manifest(root, base, manifest_file)
        info.append(f"manifest: {source}")
        failures.extend(drift_findings(root, manifest))
    except CheckError as e:
        failures.append(str(e))
    found, problems = overrides(text)
    failures.extend(problems)
    if found:
        info.append(f"{len(found)} override(s):")
        info.extend(f"  - {b}: {t}" for b, t in found)
    else:
        info.append("no overrides")
    return failures, info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check AGENTS.md, CLAUDE.md and kit text against the base branch's manifest."
    )
    ap.add_argument("dir", nargs="?", default=".", help="project root (default: .)")
    ap.add_argument("--base", help="ref holding the trusted manifest (default: origin/main, then main)")
    ap.add_argument("--manifest", help="read the trusted manifest from this file instead")
    ap.add_argument(
        "--budget", type=int, default=DEFAULT_BUDGET, help=f"AGENTS.md size budget in bytes (default {DEFAULT_BUDGET})"
    )
    args = ap.parse_args(argv)
    root = Path(args.dir).resolve()
    try:
        failures, info = run_checks(root, args.budget, args.base, args.manifest)
    except (CheckError, OSError, subprocess.CalledProcessError) as e:
        print(f"rules_check: error: {e}", file=sys.stderr)
        return 2
    for line in info:
        print(f"rules_check: {line}")
    for f in failures:
        print(f"rules_check: FAIL {f}")
    if failures:
        print(f"rules_check: failed ({len(failures)} problem(s))", file=sys.stderr)
        return 1
    print("rules_check: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
