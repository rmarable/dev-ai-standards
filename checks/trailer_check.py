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
trailer_check: exactly one allowed co-author trailer per commit.

Implements P001 Part A, "The three v1.0 checks" (1): a commit-msg hook over one message, and
CI over a range or a push (`before..after`), with the Dependabot, web-flow and root exemptions.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

ALLOWED = (
    "Co-Authored-By: Claude <noreply@anthropic.com>",
    "Co-Authored-By: Codex <noreply@openai.com>",
)
ROOT_SUBJECT = "new-claude-project: initial commit"
ZERO = "0" * 40
SCISSORS = "# ------------------------ >8 ------------------------"
CO_RE = re.compile(r"^\s*co-authored-by\s*:", re.IGNORECASE)

type Meta = dict[str, object]
type MetaLookup = Callable[[str], Meta | None]


def clean_message(msg: str, strip_comments: bool) -> str:
    lines: list[str] = []
    for ln in msg.splitlines():
        if ln.startswith(SCISSORS):
            break
        if strip_comments and ln.startswith("#"):
            continue
        lines.append(ln)
    return "\n".join(lines).strip("\n")


def check_message(msg: str, strip_comments: bool = False) -> list[str]:
    """Problems with one commit message's co-author trailers (empty list: ok)."""
    text = clean_message(msg, strip_comments)
    co = [ln.rstrip() for ln in text.splitlines() if CO_RE.match(ln)]
    if not co:
        return ["no co-author trailer (needs exactly one of the two allowed lines)"]
    problems: list[str] = []
    if len(co) > 1:
        problems.append(f"{len(co)} co-author trailers; exactly one is allowed")
    for line in co:
        if line not in ALLOWED:
            problems.append(f"trailer not allowed: '{line[:100]}'")
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    last = paragraphs[-1].splitlines() if paragraphs else []
    if not problems and co[0] not in [ln.rstrip() for ln in last]:
        problems.append("co-author trailer is not in the message's last paragraph")
    return problems


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {r.stderr.strip()[:200]}")
    return r.stdout


def commits(repo: Path, rev_args: list[str]) -> list[tuple[str, list[str], str]]:
    """(sha, parents, message) for each commit selected by rev_args, oldest first."""
    out = git(repo, "log", "--reverse", "--format=%H%x1f%P%x1f%B%x1e", *rev_args)
    result: list[tuple[str, list[str], str]] = []
    for raw in out.split("\x1e"):
        rec = raw.lstrip("\n")
        if not rec:
            continue
        sha, parents, body = rec.split("\x1f", 2)
        result.append((sha, parents.split(), body))
    return result


def github_lookup(repo_slug: str) -> MetaLookup:
    """Commit metadata (logins, verified signature) from the GitHub REST API."""
    token = os.environ.get("GITHUB_TOKEN", "")
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    if not api.startswith("https://"):
        raise RuntimeError(f"GITHUB_API_URL must be https, not {api[:40]!r}")

    def lookup(sha: str) -> Meta | None:
        url = f"{api}/repos/{repo_slug}/commits/{sha}"
        req = urllib.request.Request(url)  # noqa: S310 (https only, checked above)
        req.add_header("Accept", "application/vnd.github+json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (https only)
                data = json.load(resp)
        except OSError:
            return None
        return {
            "author_login": (data.get("author") or {}).get("login"),
            "committer_login": (data.get("committer") or {}).get("login"),
            "verified": bool(
                ((data.get("commit") or {}).get("verification") or {}).get("verified")
            ),
        }

    return lookup


def file_lookup(path: str) -> MetaLookup:
    data = json.loads(Path(path).read_text())
    return data.get


def exemption(
    sha: str, parents: list[str], message: str, meta: MetaLookup | None, creates_main: bool
) -> str | None:
    """Name of the exemption that applies to this commit, or None."""
    subject = message.splitlines()[0] if message else ""
    if not parents and subject == ROOT_SUBJECT and creates_main:
        return "launcher root commit on the push creating main"
    info = meta(sha) if meta else None
    if info and info.get("verified"):
        if info.get("author_login") == "dependabot[bot]":
            return "Dependabot (verified)"
        if len(parents) > 1 and info.get("committer_login") == "web-flow":
            return "GitHub merge by web-flow (verified)"
    return None


def push_range(
    repo: Path, before: str, after: str, ref: str, base_ref: str
) -> tuple[list[str], bool]:
    """git log arguments for the commits a push adds, and whether it creates the base branch."""
    if after == ZERO:
        return [], False
    base_name = base_ref.rsplit("/", maxsplit=1)[-1]
    creates_main = before == ZERO and ref in (f"refs/heads/{base_name}", base_name)
    if before != ZERO:
        known = (
            subprocess.run(
                ["git", "-C", str(repo), "cat-file", "-e", f"{before}^{{commit}}"],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
        if known:
            return [f"{before}..{after}"], False
        if ref in (f"refs/heads/{base_name}", base_name):
            # A force push to the base branch: the old tip wasn't fetched, and the merge-base
            # with the base ref would be `after` itself, checking nothing (K1-3).
            raise RuntimeError(
                f"before {before[:12]} not found on a push to {base_name} (force push?); can't"
                " tell which commits are new"
            )
    if creates_main:
        return [after], True
    mb = subprocess.run(
        ["git", "-C", str(repo), "merge-base", after, base_ref],
        capture_output=True,
        text=True,
        check=False,
    )
    if mb.returncode == 0 and mb.stdout.strip():
        return [f"{mb.stdout.strip()}..{after}"], False
    return [after], False


def check_commits(
    repo: Path, rev_args: list[str], meta: MetaLookup | None, creates_main: bool
) -> tuple[int, list[str]]:
    failures: list[str] = []
    selected = commits(repo, rev_args) if rev_args else []
    for sha, parents, message in selected:
        why = exemption(sha, parents, message, meta, creates_main)
        if why:
            print(f"trailer_check: {sha[:12]} exempt: {why}")
            continue
        subject = (message.splitlines() or [""])[0][:60]
        for p in check_message(message):
            failures.append(f"{sha[:12]} '{subject}': {p}")
    return len(selected), failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Exactly one allowed co-author trailer per commit.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--message-file", help="check one message file (commit-msg hook: pass $1)")
    mode.add_argument("--commit", help="check one commit")
    mode.add_argument("--range", help="check every commit in A..B")
    mode.add_argument(
        "--push", nargs=2, metavar=("BEFORE", "AFTER"), help="CI: check the commits a push adds"
    )
    ap.add_argument("--ref", default="", help="with --push: the pushed ref (e.g. refs/heads/main)")
    ap.add_argument(
        "--base-ref",
        default="origin/main",
        help="branch new branches are measured from (default origin/main)",
    )
    ap.add_argument("--repo", default=".", help="git repository (default .)")
    ap.add_argument(
        "--github-repo",
        help="OWNER/REPO: look up logins and signatures for the exemptions (uses GITHUB_TOKEN)",
    )
    ap.add_argument(
        "--meta",
        help="JSON file {sha: {author_login, committer_login, verified}} instead of the API",
    )
    args = ap.parse_args(argv)

    if args.message_file:
        problems = check_message(Path(args.message_file).read_text(), strip_comments=True)
        for p in problems:
            print(f"trailer_check: FAIL {p}", file=sys.stderr)
        if problems:
            print(
                f"trailer_check: the trailer must be exactly one of: {ALLOWED[0]} | {ALLOWED[1]}",
                file=sys.stderr,
            )
            return 1
        return 0

    repo = Path(args.repo)
    meta: MetaLookup | None = None
    if args.meta:
        meta = file_lookup(args.meta)
    try:
        if args.github_repo and not args.meta:
            meta = github_lookup(args.github_repo)
        creates_main = False
        if args.commit:
            rev_args = ["-1", args.commit]
        elif args.range:
            rev_args = [args.range]
        else:
            rev_args, creates_main = push_range(
                repo, args.push[0], args.push[1], args.ref, args.base_ref
            )
        count, failures = check_commits(repo, rev_args, meta, creates_main)
    except RuntimeError as e:
        print(f"trailer_check: error: {e}", file=sys.stderr)
        return 2
    for f in failures:
        print(f"trailer_check: FAIL {f}")
    if failures:
        print(f"trailer_check: {len(failures)} problem(s) in {count} commit(s)", file=sys.stderr)
        return 1
    print(f"trailer_check: ok ({count} commit(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
