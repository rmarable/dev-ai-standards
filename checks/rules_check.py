#!/bin/sh
# /// script
# requires-python = ">=3.12"
# ///
""":"
# sh front (POSIX sh, so it runs on a stock Mac): needs uv, then runs this file as Python >= 3.12.
# GUI git clients may not pass the shell's PATH, so uv's usual folders are tried too.
if [ -z "${DEV_AI_STANDARDS_NO_UV_SEARCH-}" ] && ! command -v uv >/dev/null 2>&1; then
  for d in "$HOME/.local/bin" "$HOME/.cargo/bin" /opt/homebrew/bin /usr/local/bin; do
    if [ -x "$d/uv" ]; then PATH="$d:$PATH"; export PATH; break; fi
  done
fi
if ! command -v uv >/dev/null 2>&1; then
  printf '%s %s\n' 'uv is required: brew install uv' \
    '(or see https://docs.astral.sh/uv/getting-started/installation/)' >&2
  exit 1
fi
# A user-level UV_PYTHON would override requires-python above.
unset UV_PYTHON
exec uv run --script "$0" "$@"
":
rules_check: checks a project's agent rule files against the dev-ai-standards kit.

Implements P001 Part A, "The three v1.0 checks" (2) and "Kit-owned and project-owned text".
Also the shared helpers (blocks, hashing, manifest) that `bin/dev-ai-standards` imports, and
the kit-upgrade rule (operator decision 2026-11-10): see `checks/README.md`, "Kit upgrades".
"""

import argparse
import hashlib
import os
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
    " .claude/rules/user-docs.md, kit blocks and the Standards line in AGENTS.md and CLAUDE.md,"
    " and .githooks/* and scripts/check (when the kit changes how its scripts start)"
)
# Files that start the kit's scripts (hooks, scripts/check). A kit release that changes how its
# scripts start (interpreter or launcher) must change them in the same PR, or commits break
# between two PRs (U1-1). Allowed only inside a valid upgrade, so only with a newer version.
LAUNCHER_DIR = ".githooks"
LAUNCHER_FILES = ("scripts/check",)


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


def is_launcher_path(path: str) -> bool:
    """A file directly in .githooks/, or scripts/check."""
    head, _, name = path.rpartition("/")
    return path in LAUNCHER_FILES or (head == LAUNCHER_DIR and bool(name))


def in_upgrade_set(path: str) -> bool:
    """The fixed set a pure upgrade may touch; never derived from any manifest (K1-2, F1-9).

    Launcher paths count only because upgrade_check also demands a strictly newer version."""
    return (
        path.startswith(STANDARDS_DIR + "/")
        or path in BLOCK_FILES
        or path in FIXED_RULES
        or is_launcher_path(path)
    )


def upgrade_check(  # noqa: PLR0912 (one linear command flow)
    root: Path, base_manifest: dict[str, str], base: str | None
) -> tuple[bool, list[str]]:
    """Decide whether this branch is a kit upgrade that may use its own manifest.

    Returns (True, [info]) when every condition holds, else (False, [reasons]). Conditions:
    every changed path is under docs/standards/ (the manifest included), a fixed rule, a file in
    .githooks/, scripts/check, or AGENTS.md or CLAUDE.md, and in those two only kit block text
    and the Standards line changed; the
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


# Multi-user readiness (operator decision 2026-11-10). A newcomer's setup needs these, so a change
# that deletes, empties or disables one fails: every file under .githooks/ and scripts/setup that
# the base commit has. Disabling covers the executable bit (git skips a hook without it) and
# dropping the kit check calls the base's copy makes (U1-8).
SETUP_PATHS = (".githooks", "scripts/setup")
SETUP_MARK = "docs/standards/checks/"
EXEC_MODE = "100755"
# Numbering: on a branch everyone writes ADR-NEW, OD-NEW or P-NEW (several: OD-NEW-1); the real
# number is assigned before merging into the default branch. Only places that hold a real number
# are scanned (U1-3): ADR file names and first lines, plan file names and header lines, and
# decision-ID definition lines (planning add-on). Text that only mentions the convention passes.
PLACEHOLDER_RE = re.compile(r"(?<![A-Za-z0-9])(?:ADR|OD|P)-NEW(?:-\d+)?(?![A-Za-z0-9])")
# A file or folder name holding a placeholder number: NEW-slug.md, ADR-NEW-slug.md, P-NEW-slug.
NEW_NAME_RE = re.compile(r"(?:(?:ADR|OD|P)-)?NEW(?:-\d+)?(?=[-_.]|$)")
# A decision-ID definition line: the ID, then a colon, at the start of a line, list item or
# heading (planning add-on, "Numbers").
DEFINITION_RE = re.compile(
    r"\s{0,3}(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)?(?:\*\*|__)?"
    r"((?:ADR|OD|P)-NEW(?:-\d+)?)(?:\*\*|__)?\s*:"
)
ADR_DIR = "docs/adr/"
PLAN_DIR = "planning-docs/"
MARKDOWN_EXTS = (".md", ".markdown", ".mdx")
CODE_SPAN_RE = re.compile(r"(`+).*?(?<!`)\1(?!`)")
DEFAULT_FALLBACKS = ("main", "master")
MAX_SCAN_BYTES = 2 * 1024 * 1024
MAX_SHOWN = 20
PEOPLE_HEADING = "## People"
PEOPLE_RE = re.compile(r"\s*[-*]\s+(Owner|Approvers)\s*:\s*(.*)")


def setup_removals(root: Path, base: str | None) -> list[str]:
    """Failures for .githooks/* and scripts/setup files the base has that are now gone, empty,
    no longer executable, or no longer call the kit checks."""
    ref = resolve_base(root, base)
    if ref is None:
        return []
    r = git(root, "ls-tree", "-r", "-z", ref, "--", *SETUP_PATHS, check=False)
    out: list[str] = []
    entries: list[tuple[str, str]] = []
    for item in r.stdout.split("\0"):
        meta, tab, rel = item.partition("\t")
        if tab:
            entries.append((rel, meta.split(" ", 1)[0]))
    for rel, mode in sorted(entries):
        p = root / rel
        why = "newcomers' setup needs it; restore it"
        if not p.is_file():
            out.append(f"{rel} deleted ({why})")
            continue
        data = p.read_bytes()
        if not data.strip():
            out.append(f"{rel} emptied ({why})")
            continue
        if mode == EXEC_MODE and not os.access(p, os.X_OK):
            out.append(f"{rel} is no longer executable (git skips it; restore it: chmod +x {rel})")
        old = show_file(root, ref, rel)
        if old is not None and SETUP_MARK in old and SETUP_MARK.encode() not in data:
            out.append(f"{rel} no longer calls {SETUP_MARK} as the base's copy does ({why})")
    return out


def default_branch(root: Path, given: str | None) -> str | None:
    """The repository's default branch: --default-branch; in GitHub Actions the workflow's
    DEFAULT_BRANCH (github.event.repository.default_branch); else origin/HEAD; else the one
    local branch of main and master that exists. None when unknown."""
    if given:
        return given
    if os.environ.get("GITHUB_EVENT_NAME") and os.environ.get("DEFAULT_BRANCH", "").strip():
        return os.environ["DEFAULT_BRANCH"].strip()
    r = git(root, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD", check=False)
    name = r.stdout.strip()
    if r.returncode == 0 and name.startswith("origin/"):
        return name.removeprefix("origin/")
    found = [b for b in DEFAULT_FALLBACKS if ref_exists(root, f"refs/heads/{b}")]
    return found[0] if len(found) == 1 else None


def merge_target(root: Path, branch: str | None) -> str | None:
    """The branch the checked state is in or is going into: --branch; in GitHub Actions a pull
    request's base branch, or the pushed branch; else git's current branch. None when detached,
    or for other CI events."""
    if branch:
        return branch
    event = os.environ.get("GITHUB_EVENT_NAME")
    if event:
        if event.startswith("pull_request"):
            return os.environ.get("GITHUB_BASE_REF", "").strip() or None
        ref = os.environ.get("GITHUB_REF", "")
        if event == "push" and ref.startswith("refs/heads/"):
            return ref.removeprefix("refs/heads/")
        return None
    r = git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False)
    return r.stdout.strip() or None


def scannable_text(rel: str, text: str) -> str:
    """Markdown text with what is only quotation removed: kit blocks, fenced code, HTML comments
    and code spans of any backtick count. Line numbers are kept."""
    if rel in BLOCK_FILES:
        for _, start, _, _, end in reversed(parse_blocks(text)):
            text = text[:start] + "\n" * text.count("\n", start, end) + text[end:]
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group().count("\n"), text, flags=re.DOTALL)
    lines = text.split("\n")
    fence: str | None = None
    for i, ln in enumerate(lines):
        m = re.match(r"\s{0,3}(`{3,}|~{3,})", ln)
        if fence is None and m:
            fence, lines[i] = m.group(1), ""
        elif fence is not None:
            if ln.strip().startswith(fence) and not ln.strip().strip(fence[0]):
                fence = None
            lines[i] = ""
    return "\n".join(CODE_SPAN_RE.sub("", ln) for ln in lines)


def numbered_dir(rel: str) -> str | None:
    """ADR_DIR or PLAN_DIR when `rel` is under one of them (where file names carry numbers)."""
    return next((d for d in (ADR_DIR, PLAN_DIR) if rel.startswith(d)), None)


def file_placeholders(root: Path, rel: str) -> list[str]:
    """Placeholder hits in one tracked file: its name (ADR and plan files), its first line (ADR
    and plan files), and decision-ID definition lines (Markdown)."""
    hits: list[str] = []
    where = numbered_dir(rel)
    if where:
        for part in rel.removeprefix(where).split("/"):
            m = NEW_NAME_RE.match(part) or PLACEHOLDER_RE.search(part)
            if m:
                hits.append(f"{rel}: {m.group()} in the file name")
                break
    p = root / rel
    if not rel.lower().endswith(MARKDOWN_EXTS) or not p.is_file():
        return hits
    if p.stat().st_size > MAX_SCAN_BYTES:
        return hits
    raw = p.read_text(encoding="utf-8", errors="replace")
    try:
        text = scannable_text(rel, raw)
    except CheckError:
        text = scannable_text(rel + ".unparsed", raw)
    lines = text.split("\n")
    first = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    for n, ln in enumerate(lines):
        m = DEFINITION_RE.match(ln)
        if where and n == first:
            hits.extend(
                f"{rel}:{n + 1}: {h.group()} in the ID line" for h in PLACEHOLDER_RE.finditer(ln)
            )
        elif m:
            hits.append(f"{rel}:{n + 1}: {m.group(1)} defined")
    return hits


def placeholder_failures(
    root: Path, branch: str | None, default: str | None
) -> tuple[list[str], list[str]]:
    """(failures, info) for number placeholders left in a change to the default branch: a pull
    request into it, a push to it, or a local check on it. Other branches pass. Tracked files
    only; kit copies (docs/standards/, the fixed rules, kit blocks) are skipped."""
    if default is None:
        return [], ["placeholder check skipped: default branch unknown (pass --default-branch)"]
    if merge_target(root, branch) != default:
        return [], []
    r = git(root, "ls-files", "-z", "--cached", check=False)
    hits: list[str] = []
    for rel in sorted({n for n in r.stdout.split("\0") if n}):
        if rel.startswith(STANDARDS_DIR + "/") or rel in FIXED_RULES:
            continue
        hits.extend(file_placeholders(root, rel))
    if not hits:
        return [], []
    shown = hits[:MAX_SHOWN] + (
        [f"and {len(hits) - MAX_SHOWN} more"] if len(hits) > MAX_SHOWN else []
    )
    return [
        f"{len(hits)} number placeholder(s) in a change to {default}: assign numbers before"
        " merging (planning add-on):",
        *(f"  {h}" for h in shown),
    ], []


# Retiring a decision (planning add-on, "Retiring a decision"): the old record says "superseded by
# <ID>" and the new one says "Supersedes <ID>". Only definition lines and ADR files are read, so
# prose that merely mentions an ID never counts.
REF_ID = r"(ADR|OD)[- ](NEW(?:-\d+)?|\d+)(?![A-Za-z0-9-])"
SUPERSEDED_BY_RE = re.compile(r"\bsuperseded\s+by\s+" + REF_ID, re.IGNORECASE)
SUPERSEDES_RE = re.compile(r"\bsupersedes\s+" + REF_ID, re.IGNORECASE)
OD_DEF_RE = re.compile(
    r"\s{0,3}(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)?(?:\*\*|__)?"
    r"OD-(NEW(?:-\d+)?|\d+)(?:\*\*|__)?\s*:"
)
LIST_ITEM_RE = re.compile(r"\s*(?:[-*+]|\d+[.)])\s")
ADR_TITLE_RE = re.compile(r"#\s*ADR[- ](NEW(?:-\d+)?|\d+)(?![A-Za-z0-9-])", re.IGNORECASE)
ADR_FILE_RE = re.compile(r"(\d+)-")


def id_key(kind: str, num: str) -> str:
    """One spelling per record: OD-12, ADR-3, OD-NEW-1 (zero padding and case dropped)."""
    kind, num = kind.upper(), num.upper()
    return f"{kind}-{int(num)}" if num.isdigit() else f"{kind}-{num}"


def scanned_markdown(root: Path) -> list[tuple[str, str]]:
    """(path, scannable text) for tracked Markdown files outside the kit copies."""
    r = git(root, "ls-files", "-z", "--cached", check=False)
    out: list[tuple[str, str]] = []
    for rel in sorted({n for n in r.stdout.split("\0") if n}):
        p = root / rel
        if rel.startswith(STANDARDS_DIR + "/") or rel in FIXED_RULES:
            continue
        if not rel.lower().endswith(MARKDOWN_EXTS) or not p.is_file():
            continue
        if p.stat().st_size > MAX_SCAN_BYTES:
            continue
        raw = p.read_text(encoding="utf-8", errors="replace")
        try:
            out.append((rel, scannable_text(rel, raw)))
        except CheckError:
            out.append((rel, scannable_text(rel + ".unparsed", raw)))
    return out


def record_definitions(root: Path) -> dict[str, list[tuple[str, int, str]]]:
    """Every decision and ADR, keyed by ID: [(path, line, text the record owns)]. A decision
    owns its definition line and the indented lines that continue it; an ADR owns its file."""
    found: dict[str, list[tuple[str, int, str]]] = {}
    for rel, text in scanned_markdown(root):
        lines = text.split("\n")
        if rel.startswith(ADR_DIR) and "/" not in rel.removeprefix(ADR_DIR):
            first = next((ln for ln in lines if ln.strip()), "")
            m = ADR_TITLE_RE.match(first.strip())
            name = rel.removeprefix(ADR_DIR)
            f = ADR_FILE_RE.match(name)
            key = id_key("ADR", m.group(1)) if m else id_key("ADR", f.group(1)) if f else None
            if key:
                found.setdefault(key, []).append((rel, 1, text))
            continue
        for n, ln in enumerate(lines):
            m = OD_DEF_RE.match(ln)
            if not m:
                continue
            own = [ln]
            for nxt in lines[n + 1 :]:
                if not nxt.strip() or not nxt[0].isspace() or LIST_ITEM_RE.match(nxt):
                    break
                own.append(nxt)
            found.setdefault(id_key("OD", m.group(1)), []).append((rel, n + 1, "\n".join(own)))
    return found


def supersede_failures(root: Path) -> list[str]:
    """Supersede links that point at no record or lack the matching link back, and decision or
    ADR IDs defined more than once. Placeholder IDs are matched as written, never as duplicates."""
    defs = record_definitions(root)
    out: list[str] = []
    for key, places in sorted(defs.items()):
        if len(places) > 1 and "NEW" not in key:
            where = ", ".join(f"{rel}:{n}" for rel, n, _ in places)
            out.append(f"{key} is defined {len(places)} times ({where}); keep one, link the rest")
    for key, places in sorted(defs.items()):
        rel, n, text = places[0]
        for regex, back, word, back_word in (
            (SUPERSEDED_BY_RE, SUPERSEDES_RE, "superseded by", "Supersedes"),
            (SUPERSEDES_RE, SUPERSEDED_BY_RE, "supersedes", "superseded by"),
        ):
            for m in regex.finditer(text):
                other = id_key(m.group(1), m.group(2))
                if other == key:
                    continue
                if other not in defs:
                    out.append(f"{rel}:{n}: {key} {word} {other}, which isn't defined")
                    continue
                if not any(
                    id_key(b.group(1), b.group(2)) == key for b in back.finditer(defs[other][0][2])
                ):
                    o_rel, o_n, _ = defs[other][0]
                    out.append(
                        f"{rel}:{n}: {key} {word} {other}, but {other} ({o_rel}:{o_n}) doesn't"
                        f' say "{back_word} {key}"'
                    )
    return out


# Every new file under planning-docs/ carries an ID: a top-level plan, milestone or release plan
# by its name and first line, anything else by the plan folder it sits in (planning add-on, IDs).
PLAN_KINDS = {
    "milestones": r"M\d+",
    "releases": r"v\d+\.\d+\.\d+",
    "": r"P(?:\d+|-NEW(?:-\d+)?)",
}
PLAN_EXAMPLES = {
    "milestones": "milestones/M<n>-<slug>.md",
    "releases": "releases/v<X.Y.Z>-<slug>.md",
    "": "P<nnn>-<slug>.md",
}
PLAN_INDEX = PLAN_DIR + "README.md"


def added_paths(root: Path, base: str) -> list[str]:
    """Files added since the merge-base with `base`, untracked files included."""
    mb = git(root, "merge-base", base, "HEAD", check=False)
    since = mb.stdout.strip() if mb.returncode == 0 and mb.stdout.strip() else base
    diff = git(root, "diff", "--name-only", "--no-renames", "--diff-filter=A", since)
    extra = git(root, "ls-files", "--others", "--exclude-standard")
    return sorted({p for p in (diff.stdout + extra.stdout).splitlines() if p.strip()})


def plan_id_problem(root: Path, rel: str) -> str | None:
    """Why a file under planning-docs/ has no usable ID, or None."""
    if rel == PLAN_INDEX:
        return None
    parts = rel.removeprefix(PLAN_DIR).split("/")
    kind = parts[0] if parts[0] in PLAN_KINDS and len(parts) > 1 and parts[0] else ""
    rest = parts[1:] if kind else parts
    pat = PLAN_KINDS[kind]
    example = PLAN_EXAMPLES[kind]
    if len(rest) == 1:
        m = re.match(rf"({pat})-[^/]+\.md$", rest[0])
        if not m:
            return (
                f"{rel}: no ID in the name (name it {example}, or put it in a folder named"
                " after its plan's ID)"
            )
        plan_id, doc = m.group(1), rel
    else:
        m = re.match(rf"({pat})(?:-|$)", rest[0])
        if not m:
            return f"{rel}: the folder {rest[0]}/ doesn't start with a plan ID ({example})"
        if rest[1:] != ["README.md"]:
            return None
        plan_id, doc = m.group(1), rel
    text = (root / doc).read_text(errors="replace")
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    if not re.match(rf"{re.escape(plan_id)}(?![\w.-])", first.strip()):
        return f"{doc}:1: the first line must start with its ID, {plan_id}"
    return None


def plan_id_failures(root: Path, base: str | None) -> list[str]:
    """Files added under planning-docs/ without an ID. Existing files are never checked: the
    planning add-on never renames or moves them."""
    ref = resolve_base(root, base)
    if ref is None:
        return []
    out = []
    for rel in added_paths(root, ref):
        if rel.startswith(PLAN_DIR) and (root / rel).is_file():
            problem = plan_id_problem(root, rel)
            if problem:
                out.append(problem)
    return out


def people_section(text: str) -> str | None:
    """The '## People' section of AGENTS.md text (heading excluded), or None."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.rstrip() == PEOPLE_HEADING), None)
    if start is None:
        return None
    body: list[str] = []
    for ln in lines[start + 1 :]:
        if ln.startswith("# ") or ln.startswith("## "):
            break
        body.append(ln.rstrip())
    return "\n".join(body).strip("\n")


def parse_people(section: str) -> dict[str, list[str]]:
    """Owner and Approvers from a People section: GitHub logins, '@' and backticks dropped."""
    found: dict[str, list[str]] = {"Owner": [], "Approvers": []}
    for ln in section.splitlines():
        m = PEOPLE_RE.fullmatch(ln)
        if m:
            names = [n.strip().strip("`").lstrip("@") for n in m.group(2).split(",")]
            found[m.group(1)].extend(n for n in names if n)
    return found


def people_ref(root: Path, default: str | None) -> str | None:
    """origin/<default>, else <default>: the only copies whose People count."""
    if default is None:
        return None
    return next((r for r in (f"origin/{default}", default) if ref_exists(root, r)), None)


def people_changed(root: Path, base: str | None, default: str | None) -> list[str]:
    """A warning when this change edits the People section of AGENTS.md (U1-4). Never fails:
    the change takes effect only once merged, and the owner's approval is a human check."""
    ref = resolve_base(root, base)
    agents = root / "AGENTS.md"
    if ref is None or not agents.is_file():
        return []
    mb = git(root, "merge-base", ref, "HEAD", check=False)
    since = mb.stdout.strip() if mb.returncode == 0 and mb.stdout.strip() else ref
    old = show_file(root, since, "AGENTS.md")
    if old is None or people_section(old) == people_section(agents.read_text()):
        return []
    return [
        "People changed: needs the owner's approval (merge by the owner listed on"
        f" {default or 'the default branch'})"
    ]


def repo_checks(
    root: Path, base: str | None, branch: str | None, default: str | None
) -> tuple[list[str], list[str], list[str]]:
    """(failures, warnings, info): setup files kept, placeholders, supersede links, plan IDs,
    People changes (repos only)."""
    if not is_git_repo(root):
        return [], [], []
    default = default_branch(root, default)
    fails, info = placeholder_failures(root, branch, default)
    return (
        [
            *setup_removals(root, base),
            *fails,
            *supersede_failures(root),
            *plan_id_failures(root, base),
        ],
        people_changed(root, base, default),
        info,
    )


def show_people(root: Path, default: str | None) -> int:
    """Print Owner and Approvers from the default branch's AGENTS.md, never the working tree."""
    if not is_git_repo(root):
        print("rules_check: error: --people needs a git repo", file=sys.stderr)
        return 2
    ref = people_ref(root, default_branch(root, default))
    text = show_file(root, ref, "AGENTS.md") if ref else None
    section = people_section(text) if text is not None else None
    if section is None:
        print(
            "rules_check: error: no People section on the default branch"
            f" ({ref or 'default branch unknown: pass --default-branch'})",
            file=sys.stderr,
        )
        return 1
    found = parse_people(section)
    print(f"rules_check: People from {ref}:AGENTS.md (the working tree never counts)")
    print(f"Owner: {', '.join(found['Owner']) or '(none)'}")
    print(f"Approvers: {', '.join(found['Approvers']) or '(none)'}")
    return 0


def run_checks(
    root: Path,
    budget: int,
    base: str | None,
    manifest_file: str | None,
    branch: str | None = None,
    default: str | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Return (failures, warnings, info lines). Warnings never fail the run."""
    failures, warnings, info = repo_checks(root, base, branch, default)
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    if not claude.is_file():
        failures.append("CLAUDE.md missing")
    elif not has_import(claude.read_text()):
        failures.append("CLAUDE.md does not import AGENTS.md (no '@AGENTS.md' line)")
    if not agents.is_file():
        failures.append("AGENTS.md missing")
        return failures, warnings, info
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
    return failures, warnings, info


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
        "--branch",
        help=(
            "branch the change is in or goes into, for the placeholder check (default: in GitHub"
            " Actions a pull request's base branch or the pushed branch; else git's current"
            " branch)"
        ),
    )
    ap.add_argument(
        "--default-branch",
        help=(
            "the repository's default branch (default: in GitHub Actions the DEFAULT_BRANCH"
            " variable; else origin/HEAD; else main or master, whichever exists)"
        ),
    )
    ap.add_argument(
        "--people",
        action="store_true",
        help="print Owner and Approvers from the default branch's AGENTS.md, then exit",
    )
    ap.add_argument(
        "--budget",
        type=int,
        default=DEFAULT_BUDGET,
        help=f"AGENTS.md size budget in bytes (default {DEFAULT_BUDGET})",
    )
    args = ap.parse_args(argv)
    root = Path(args.dir).resolve()
    try:
        if args.people:
            return show_people(root, args.default_branch)
        failures, warnings, info = run_checks(
            root, args.budget, args.base, args.manifest, args.branch, args.default_branch
        )
    except (CheckError, OSError, subprocess.CalledProcessError) as e:
        print(f"rules_check: error: {e}", file=sys.stderr)
        return 2
    for line in info:
        print(f"rules_check: {line}")
    for w in warnings:
        print(f"rules_check: WARN {w}")
        if os.environ.get("GITHUB_ACTIONS") == "true":
            # A workflow annotation: shown on the run and the pull request, not only in the log.
            print(f"::warning title=rules-check::{w}")
    for f in failures:
        print(f"rules_check: FAIL {f}")
    if failures:
        print(f"rules_check: failed ({len(failures)} problem(s))", file=sys.stderr)
        return 1
    print("rules_check: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
