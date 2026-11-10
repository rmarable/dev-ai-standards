#!/usr/bin/env python3
"""rules_check: checks a project's agent rule files against the dev-ai-standards kit.

Implements P001 Part A, "The three v1.0 checks" (2) and "Kit-owned and project-owned text".
Also the shared helpers (blocks, hashing, manifest) that `bin/dev-ai-standards` imports, and
the kit-upgrade rule (operator decision 2026-11-10): see `checks/README.md`, "Kit upgrades".
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
BLOCK_FILES = ("AGENTS.md", "CLAUDE.md")
STANDARDS_DIR = "docs/standards"
# The state-file path rule: kit text outside docs/standards/ (Claude Code reads rules only from
# .claude/rules/). One fixed literal, in the manifest and the upgrade set (F1-9).
STATE_RULE = ".claude/rules/state-file.md"
# The user-docs path rule (doc rules, 2026-11-10): written like STATE_RULE, the same treatment.
USER_DOCS_RULE = ".claude/rules/user-docs.md"
FIXED_RULES = (STATE_RULE, USER_DOCS_RULE)
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


def manifest_key_problem(key: str) -> str | None:
    """Why `key` can't be a manifest entry, or None.

    Allowed: a plain relative path under docs/standards/ (not the manifest itself), the one
    fixed paths in FIXED_RULES, or AGENTS.md#<block> / CLAUDE.md#<block> with a known block name.
    Nothing else, ever: the manifest never decides which other paths count as kit text (K1-2,
    K1-5, F1-9).
    """
    if key in FIXED_RULES:
        return None
    if "#" in key:
        fname, _, name = key.partition("#")
        if fname in BLOCK_FILES and name in BLOCK_NAMES:
            return None
        return "not AGENTS.md#<block> or CLAUDE.md#<block> with a known block name"
    parts = key.split("/")
    if (
        "\\" in key
        or key.startswith("/")
        or any(p in ("", ".", "..") for p in parts)
        or not key.startswith(STANDARDS_DIR + "/")
        or key == MANIFEST_PATH
    ):
        return f"not a plain path under {STANDARDS_DIR}/"
    return None


def parse_manifest(text: str) -> dict[str, str]:
    """Map path (or AGENTS.md#block) to sha256 hex. Refuses keys outside the fixed kit set."""
    entries: dict[str, str] = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        m = re.fullmatch(r"([0-9a-f]{64})  (\S.*)", line)
        if not m:
            raise CheckError(f"manifest line {n} is malformed")
        why = manifest_key_problem(m.group(2))
        if why:
            raise CheckError(f"manifest line {n}: '{m.group(2)[:80]}' is {why}")
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
    return (
        git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).returncode
        == 0
    )


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


def drift_findings(root: Path, manifest: dict[str, str]) -> list[str]:  # noqa: PLR0912 (one pass per key kind)
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


STANDARDS_LINE_RE = re.compile(r"(?m)^Standards: dev-ai-standards v(\S+) \(.*\)[ \t]*$")
VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?")
UPGRADE_SCOPE_MSG = (
    "kit upgrade PRs may change only docs/standards/**, .claude/rules/state-file.md,"
    " .claude/rules/user-docs.md, and kit blocks and the Standards line in AGENTS.md and CLAUDE.md"
)


def standards_version(text: str) -> str | None:
    m = STANDARDS_LINE_RE.search(text)
    return m.group(1) if m else None


def semver_key(version: str) -> tuple[object, ...]:
    """Sort key for semantic-version precedence (a missing patch counts as 0)."""
    m = VERSION_RE.fullmatch(version)
    if not m:
        raise CheckError(f"'{version}' is not a semantic version")
    core = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
    if m.group(4) is None:
        return (*core, 1, ())
    ids = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in m.group(4).split("."))
    return (*core, 0, ids)


def project_text(text: str, fname: str) -> str:
    """The project-owned part of AGENTS.md or CLAUDE.md: kit blocks and Standards line removed."""
    for _, start, _, _, end in reversed(parse_blocks(text)):
        text = text[:start] + text[end:]
    if fname == "AGENTS.md":
        text = STANDARDS_LINE_RE.sub("", text, count=1)
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")


def changed_paths(root: Path, base: str) -> tuple[list[str], str]:
    """(paths that differ between the merge-base with `base` and the working tree, untracked
    included; the commit compared with)."""
    mb = git(root, "merge-base", base, "HEAD", check=False)
    since = mb.stdout.strip() if mb.returncode == 0 and mb.stdout.strip() else base
    diff = git(root, "diff", "--name-only", "--no-renames", since)
    extra = git(root, "ls-files", "--others", "--exclude-standard")
    return sorted({p for p in (diff.stdout + extra.stdout).splitlines() if p.strip()}), since


def resolve_base(root: Path, base: str | None) -> str | None:
    if not is_git_repo(root):
        return None
    if base:
        return base if ref_exists(root, base) else None
    return next((r for r in BASE_CANDIDATES if ref_exists(root, r)), None)


def in_upgrade_set(path: str) -> bool:
    """The fixed set a pure upgrade may touch; never derived from any manifest (K1-2, F1-9)."""
    return path.startswith(STANDARDS_DIR + "/") or path in BLOCK_FILES or path in FIXED_RULES


def upgrade_check(  # noqa: PLR0912 (one linear command flow)
    root: Path, base_manifest: dict[str, str], base: str | None
) -> tuple[bool, list[str]]:
    """Decide whether this branch is a kit upgrade that may use its own manifest.

    Returns (True, [info]) when every condition holds, else (False, [reasons]). Conditions:
    every changed path is under docs/standards/ (the manifest included) or is AGENTS.md or
    CLAUDE.md, and in those two only kit block text and the Standards line changed; the
    Standards line names a strictly newer version than the base's; the head's kit files and
    blocks match the head's manifest (whose keys parse_manifest has already limited).
    """
    ref = resolve_base(root, base)
    if ref is None:
        return False, ["kit upgrade needs a base branch to compare with (none found)"]
    head_mpath = root / MANIFEST_PATH
    if not head_mpath.is_file():
        return False, [f"kit upgrade: no {MANIFEST_PATH} on this branch"]
    try:
        head_manifest = parse_manifest(head_mpath.read_text())
    except CheckError as e:
        return False, [f"kit upgrade: head {e}"]
    paths, since = changed_paths(root, ref)
    reasons: list[str] = []
    outside = [p for p in paths if not in_upgrade_set(p)]
    if outside:
        shown = ", ".join(outside[:5]) + (
            f" and {len(outside) - 5} more" if len(outside) > 5 else ""
        )
        reasons.append(f"{UPGRADE_SCOPE_MSG} (also changed: {shown})")
    for fname in BLOCK_FILES:
        if fname not in paths:
            continue
        old = show_file(root, since, fname)
        new_path = root / fname
        if old is None or not new_path.is_file():
            reasons.append(f"{UPGRADE_SCOPE_MSG} ({fname} added or removed)")
            continue
        try:
            same = project_text(old, fname) == project_text(new_path.read_text(), fname)
        except CheckError as e:
            reasons.append(f"kit upgrade: {fname}: {e}")
            continue
        if not same:
            reasons.append(f"{UPGRADE_SCOPE_MSG} ({fname}: text outside kit blocks changed)")
    old_agents = show_file(root, since, "AGENTS.md")
    agents = root / "AGENTS.md"
    old_v = standards_version(old_agents) if old_agents is not None else None
    new_v = standards_version(agents.read_text()) if agents.is_file() else None
    if old_v is None or new_v is None:
        reasons.append("kit upgrade: the Standards line is missing on the base or this branch")
    else:
        try:
            newer = semver_key(new_v) > semver_key(old_v)
        except CheckError as e:
            newer = False
            reasons.append(f"kit upgrade: Standards line: {e}")
        else:
            if not newer:
                reasons.append(
                    "kit upgrade PRs must name a strictly newer version on the Standards line"
                    f" (base v{old_v}, this branch v{new_v})"
                )
    head_findings = drift_findings(root, head_manifest)
    if head_findings:
        reasons.append(
            "kit upgrade: kit files and blocks don't match this branch's manifest"
            f" ({len(head_findings)} finding(s))"
        )
        reasons.extend(f"  {f}" for f in head_findings)
    if reasons:
        return False, reasons
    return True, [
        f"kit upgrade v{old_v} -> v{new_v}: using this branch's manifest (only kit text changed)"
    ]


def is_upgrade_attempt(root: Path, base_manifest: dict[str, str], base: str | None) -> bool:
    """A branch whose manifest or Standards version differs from the base's is trying an upgrade."""
    head_mpath = root / MANIFEST_PATH
    try:
        if head_mpath.is_file() and parse_manifest(head_mpath.read_text()) != base_manifest:
            return True
    except CheckError:
        return True
    ref = resolve_base(root, base)
    agents = root / "AGENTS.md"
    if ref is None or not agents.is_file():
        return False
    old = show_file(root, ref, "AGENTS.md")
    return old is not None and standards_version(old) != standards_version(agents.read_text())


def kit_findings(
    root: Path, manifest: dict[str, str], source: str, base: str | None
) -> tuple[list[str], list[str]]:
    """(findings, info) for kit files and blocks against the trusted manifest, with upgrades.

    A branch whose manifest or Standards version differs from the base's always goes through
    the upgrade rule, even when its kit text still matches the base manifest: a manifest edit
    outside an upgrade fails (K1-5).
    """
    findings = drift_findings(root, manifest)
    from_base = not source.startswith("working copy")
    if not (from_base and is_upgrade_attempt(root, manifest, base)):
        return findings, []
    ok, lines = upgrade_check(root, manifest, base)
    if ok:
        return [], lines
    head = (
        "the manifest or the Standards line changed outside a valid kit upgrade; checked against"
        " the base manifest instead:"
    )
    return [f"kit upgrade refused: {head}", *lines, *findings], []


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
            for raw in PATHLIKE_RE.findall(cells[col]):
                token = raw.split("#", 1)[0].removeprefix("./")
                if "://" in token or "*" in token or not token:
                    continue
                if "/" in token or re.search(r"\.[A-Za-z0-9]+$", token):
                    paths.append(token)
    return paths


def strip_unloaded(text: str) -> str:
    """Text with HTML comments and fenced code blocks removed: Claude Code evaluates no
    imports there (K1-8)."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    out: list[str] = []
    fence: str | None = None
    for ln in text.splitlines():
        m = re.match(r"\s{0,3}(`{3,}|~{3,})", ln)
        if fence is None and m:
            fence = m.group(1)
            continue
        if fence is not None:
            if ln.strip().startswith(fence[0] * len(fence)) and not ln.strip().strip(fence[0]):
                fence = None
            continue
        out.append(ln)
    return "\n".join(out)


def has_import(claude_md: str) -> bool:
    return any(ln.strip() == "@AGENTS.md" for ln in strip_unloaded(claude_md).splitlines())


# Kit rows every read-before table must carry when the file is in the trusted manifest (K2-3).
KIT_READ_BEFORE = (
    "docs/standards/refs/honesty.md",
    "docs/standards/refs/outside-sources.md",
    "docs/standards/refs/user-docs.md",
    "docs/standards/checks/README.md",
    "docs/standards/refs/diff-review.md",
)


def missing_kit_rows(text: str, manifest: dict[str, str]) -> list[str]:
    have = set(read_before_paths(text))
    return [p for p in KIT_READ_BEFORE if p in manifest and p not in have]


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
    missing_paths = [p for p in read_before_paths(text) if not (root / p).exists()]
    upgrade_ok = False
    try:
        manifest, source = load_manifest(root, base, manifest_file)
        info.append(f"manifest: {source}")
        ref = resolve_base(root, base)
        if ref is not None:
            sha = git(root, "rev-parse", "--short", f"{ref}^{{commit}}", check=False).stdout.strip()
            info.append(f"compared with {ref} ({sha or 'unknown'})")
        findings, notes = kit_findings(root, manifest, source, base)
        # Notes come back only for a valid kit upgrade.
        upgrade_ok = bool(notes)
        info.extend(notes)
        failures.extend(findings)
        failures.extend(
            f"read-before table has no row for {p} (kit row)"
            for p in missing_kit_rows(text, manifest)
        )
    except CheckError as e:
        failures.append(str(e))
    # A valid upgrade may remove a kit file its row names; the row is project text the upgrade
    # can't edit, so a later PR drops it (F1-11).
    for p in missing_paths:
        if upgrade_ok and p in KIT_READ_BEFORE:
            info.append(
                f"read-before kit row {p}: file removed by this kit upgrade; drop the row next"
            )
        else:
            failures.append(f"read-before table path missing: {p}")
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
    ap.add_argument(
        "--base",
        help=(
            "base ref: holds the trusted manifest unless --manifest is given, and is what a kit"
            " upgrade"
            " is compared with (default: origin/main, then main). CI passes the PR base, or on a"
            " push"
            " the commit before the push"
        ),
    )
    ap.add_argument("--manifest", help="read the trusted manifest from this file instead")
    ap.add_argument(
        "--budget",
        type=int,
        default=DEFAULT_BUDGET,
        help=f"AGENTS.md size budget in bytes (default {DEFAULT_BUDGET})",
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
