# Checks

The three v1.0 checks (P001 Part A, "The three v1.0 checks"), how they're wired, and the
enforcement paths the merge check names. Python 3.12 standard library only; each script has
`--help`. In a project they live in `docs/standards/checks/` (kit-owned, copied by `apply`).

## Enforcement paths

The merge check (core, Enforcement) names every changed path below. None of them is ever docs
only, whatever a project's docs-only list says; on a `codex/*` branch any change to one fails the
merge check.

- `AGENTS.md`, `CLAUDE.md`
- `.claude/**`, `.githooks/**`, and every script a hook calls
- `checks/**`, `bin/**`, `scripts/check`
- `.github/**` (workflows, the docs-only list, `CODEOWNERS`)
- `.codex/**`, `.agents/**`
- `.gitattributes`, `CODEOWNERS` (any location)
- `docs/standards/**`

The merge check also fails on a workflow job `name:` equal to a required status context
(`rules-check`; with a local gate, `local-gate`), and, on `codex/*`, on a change to a plan's
Decisions or approval lines.

## `trailer_check.py`

Exactly one co-author trailer per commit, and it must be one of:

```text
Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
```

It sits in the message's last paragraph; any other `Co-Authored-By:` line (another name, a model
name, a second trailer) fails.

| Mode | Use |
|---|---|
| `--message-file <file>` | `commit-msg` hook; `#` comment lines and text below the scissors line are ignored |
| `--commit <sha>` | one commit |
| `--range A..B` | every commit in `A..B` (CI on a pull request: base..head) |
| `--push BEFORE AFTER --ref <ref> [--base-ref origin/main]` | CI on a push: only the commits the push adds |

Push ranges: `before..after`; a new branch (`before` all zeros) from its merge-base with the base
branch; an orphan branch from its root; a deletion (`after` all zeros) checks nothing.

Exemptions, only in the commit modes:
- Dependabot: GitHub author login `dependabot[bot]` with a verified signature.
- GitHub's merge commits: more than one parent, committer login `web-flow`, verified signature
  (unproven until A4). An unsigned commit that only claims GitHub's name fails.
- The launcher's root commit: subject `new-claude-project: initial commit`, no parents, on the
  push that creates the base branch (`before` all zeros, `--ref refs/heads/main`). The same subject
  on a later commit or an orphan branch's root fails.

Logins and signatures come from the GitHub API (`--github-repo OWNER/REPO`, token in
`GITHUB_TOKEN`), or from a JSON file (`--meta`, for tests). Without either, no Dependabot or
web-flow exemption applies.

## `rules_check.py`

Run as `rules_check.py [--base REF | --manifest FILE] [--budget BYTES] [<dir>]`. Fails when:
- `CLAUDE.md` has no line that is exactly `@AGENTS.md`;
- `AGENTS.md` is over the size budget (default 24 KiB, well under Codex's 32 KiB combined chain;
  one number per project, set with `--budget` in the workflow);
- a backticked path in the `Read` column of a read-before table doesn't exist (skill names and
  URLs are skipped);
- a kit file or a kit block in `AGENTS.md` or `CLAUDE.md` differs from the trusted manifest, is
  missing, or isn't listed (including any file under `docs/standards/` the manifest doesn't name);
- `## Overrides` appears more than once, or a line in it isn't `- <block name>: <text>` with a
  known block name.

It always prints the overrides it found. The trusted manifest is `--manifest FILE` (CI: the base
branch's copy), else `--base REF`, else `origin/main`, then `main`. Only when no base branch exists,
or the base has no manifest yet (first adoption), does it read the working copy, and it says so.
A branch's edit to its own manifest therefore changes nothing.

**Kit updates:** a branch that re-runs `apply` for a new kit version changes kit text and the
manifest together, so `rules_check` fails on that branch until it merges (the base manifest still
holds the old hashes). Merging such a PR needs the operator's decision each time; unresolved, see
the kit's open questions.

Manifest format, written only by `apply`: one line per kit file or block,
`<sha256 hex>  <path>` or `<sha256 hex>  <AGENTS.md|CLAUDE.md>#<block>`. A block's hash covers the
exact text between its two markers, markers excluded.

## `state_check.py`

Warn-only, sizes only (state-file add-on): file over 8 KiB (8,192 bytes), a line over 300
characters, Next steps or Open questions over 10 entries, Recent progress over 16. Entries are
top-level `- ` lines under each `## ` heading. It never fails.

| Mode | Reports | Exit |
|---|---|---|
| `state_check.py [<file>]` | the whole file (default: `CLAUDE-STATE.md` in the main checkout, found with `git rev-parse --git-common-dir`) | 0 |
| `--hook session-start` | the whole file, on stdout | 0 |
| `--hook post-tool-use` | only that Edit or Write: long lines inside the edit, caps of the sections it touched, the file size if the edit grew it | 2 with warnings on stderr (shows them to Claude; the edit already happened), else 0 |

## Hook mechanics

Hooks are reminders, not boundaries: `--no-verify` and a branch's own edits skip them; CI is the
check that reports.

**commit-msg** (git): in `.githooks/commit-msg`, with `git config core.hooksPath .githooks`:

```sh
#!/bin/sh
exec python3 docs/standards/checks/trailer_check.py --message-file "$1"
```

**Claude Code** (project `.claude/settings.json`): the path filter goes in `if`, since `matcher`
tests only the tool name (A0 row 12).

```json
{
  "hooks": {
    "PostToolUse": [
      {"matcher": "Edit|Write", "hooks": [{"type": "command", "if": "Edit(**/CLAUDE-STATE.md)",
        "command": "python3 \"$CLAUDE_PROJECT_DIR\"/docs/standards/checks/state_check.py --hook post-tool-use"}]}
    ],
    "SessionStart": [
      {"hooks": [{"type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR\"/docs/standards/checks/state_check.py --hook session-start"}]}
    ]
  }
}
```

The exact `if` form for Write as well as Edit is unproven until A4; the script itself ignores any
file not named `CLAUDE-STATE.md`, so a broader filter is harmless.

**CI** (`templates/ci/rules-check.yml`, job `rules-check`): no path filter; takes
`docs/standards/checks/` and the manifest from the base branch, then runs `trailer_check` and
`rules_check`. Detection only: a branch can edit its own copy of the workflow.

## `bin/gate-status` (high-stakes)

Posts the `local-gate` commit status. Always run the base branch's copy, for example:

```sh
git fetch origin
git show origin/main:docs/standards/bin/gate-status > "$TMPDIR/gate-status"
python3 "$TMPDIR/gate-status" --check
```

The script also re-runs the base copy itself when the copy it was started from differs; that guards
against a stale or edited copy, not against a hostile one, which is why the command above comes
first. The docs-only list (`.github/docs-only-paths`, project-owned path prefixes) is read only
from the base branch. Both sides of every rename are checked; copies, binaries, submodules and
symlinks are never docs only, nor is any enforcement path. `--passed N --skipped 0` refuses a dirty
tree, a `HEAD` other than the PR head, or any skip; it can't prove the run happened, so post only
after the real full run. `--verify` checks the status's creator is the operator's login and no
check run has the same name.
