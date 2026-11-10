# Checks

The three v1.0 checks (P001 Part A, "The three v1.0 checks"), the hook helpers (`secret_scan`,
`shell_lint`, `pre_commit`), how they're wired, and the enforcement paths the merge check names.
Standard library only; they run on Python 3.9 (stock macOS `python3`) through 3.12, and the kit's
`scripts/check` runs the tests on both. Each script has `--help`. In a project they live in
`docs/standards/checks/` (kit-owned, copied by `apply`).

## Enforcement paths

The merge check (core, Enforcement) names every changed path below. None of them is ever docs
only, whatever a project's docs-only list says; on a `codex/*` branch any change to one fails the
merge check.

- `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `CLAUDE.local.md`, `CODEOWNERS` and
  `.gitattributes` at any depth (Claude Code and Codex read nested instruction files; a nested
  `.gitattributes` changes how git sees files)
- anything under a `.claude/`, `.codex/`, `.agents/` or `.githooks/` folder at any depth, and every
  script a hook calls
- `checks/**`, `bin/**`, `scripts/check`
- `.github/**` (workflows, the docs-only list)
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
branch; an orphan branch from its root; a deletion (`after` all zeros) checks nothing. A push to
the base branch whose `before` isn't in the fetched history (a force push) fails: the commits it
adds can't be told apart.

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

Run as `rules_check.py [--base REF] [--manifest FILE] [--budget BYTES] [<dir>]`. Fails when:
- `CLAUDE.md` has no line that is exactly `@AGENTS.md` outside fenced code and HTML comments
  (Claude Code evaluates no imports there);
- `AGENTS.md` is over the size budget (default 24 KiB, well under Codex's 32 KiB combined chain;
  one number per project, set with `--budget` in the workflow);
- a backticked path in the `Read` column of a read-before table doesn't exist (skill names and
  URLs are skipped), or a kit row is missing: honesty, outside sources and this file, plus
  diff-review in high-stakes projects (rows the trusted manifest selects; `apply` adds them);
- a kit file or a kit block in `AGENTS.md` or `CLAUDE.md` differs from the trusted manifest, is
  missing, or isn't listed (including any file under `docs/standards/` the manifest doesn't name),
  unless the branch is a kit upgrade (below);
- `## Overrides` appears more than once, or a line in it isn't `- <block name>: <text>` with a
  known block name.

It always prints the overrides it found. The trusted manifest is `--manifest FILE` (CI: the base
branch's copy), else `--base REF`, else `origin/main`, then `main`. Only when no base branch exists,
or the base has no manifest yet (first adoption), does it read the working copy, and it says so.
A branch's edit to its own manifest therefore changes nothing, except in a kit upgrade.

**Kit upgrades** (operator decisions 2026-11-10): a branch that re-runs `apply` for a new kit
version changes kit text and the manifest together. `rules_check` then checks against the branch's
own manifest instead of the base's only when all of these hold:
- every changed path is in a fixed set, never read from any manifest: `docs/standards/**` (the
  manifest included), `.claude/rules/state-file.md`, `.claude/rules/user-docs.md`, `AGENTS.md` and `CLAUDE.md`; in the last two, only text inside kit blocks and
  the `Standards:` line changed;
- the `Standards:` line names a strictly newer version (semantic-version order) than the base's;
- the branch's kit files and blocks match the branch's manifest.

Changed paths are those between the merge-base with the base ref (`--base`, else `origin/main`,
then `main`) and the working tree, untracked files included; CI passes `--base` with the PR's base.
Any branch whose manifest or version differs from the base's goes through this rule, even if its
kit text still matches the base manifest, so a manifest edit outside an upgrade fails. A miss fails
with the reason (for example "kit upgrade PRs may change only docs/standards/** ... (also changed:
...)") plus the usual findings against the base manifest. So the rest of what `apply` writes on an
upgrade (`.gitignore` lines, `.claude/settings.json`, hooks, `scripts/check`, new read-before
rows) goes in its own PR, as does the changelog line.
`dev-ai-standards drift` applies the same rule. Within the rule, a pure upgrade may rewrite or
remove any kit file or block, the checks included, and nothing ties it to a real kit release: the
PR review compares the kit diff with the kit's `CHANGELOG.md`.

Manifest format, written only by `apply`: one line per kit file or block,
`<sha256 hex>  docs/standards/<path>`, `<sha256 hex>  .claude/rules/state-file.md` or
`.claude/rules/user-docs.md` (two fixed literals: Claude Code reads rules only from
`.claude/rules/`) or
`<sha256 hex>  <AGENTS.md|CLAUDE.md>#<block>`. A block's hash covers the exact text between its two
markers, markers excluded. Any other key (`..`, an absolute path, a backslash, another path outside
`docs/standards/`, an unknown block) fails the check and stops `apply`.

## `state_check.py`

Warn-only, sizes only (state-file add-on): file over 8 KiB (8,192 bytes), a line over 300
characters, Next steps or Open questions over 10 entries, Recent progress over 16. Entries are
top-level `- ` lines under each `## ` heading. It never fails.

| Mode | Reports | Exit |
|---|---|---|
| `state_check.py [<file>]` | the whole file (default: `CLAUDE-STATE.md` in the main checkout, found with `git rev-parse --git-common-dir`) | 0 |
| `--hook session-start` | the whole file, on stdout | 0 |
| `--hook post-tool-use` | only that Edit or Write: long lines inside the edit, caps of the sections it touched, the file size if the edit grew it | 2 with warnings on stderr (shows them to Claude; the edit already happened), else 0 |

## `secret_scan.py`

Looks for credential shapes in the lines a change adds: AWS access key ids, private key blocks,
GitHub, Anthropic, OpenAI-style and Slack tokens. A tripwire, not a guarantee. Prints file, line
number and kind, never any line content. The diff is read hunk by hunk: `+++ ` is a file header
only outside a hunk, and inside one every line starting with `+` is an added line (so `++ x` adds
`+ x`); the staged diff uses fixed `a/` `b/` prefixes whatever the git config says. `--staged` (default) scans the staged diff; `--diff-file F` a saved diff.
Exit 1 on a hit. Before a hooks-off commit of Codex work, Claude runs it and `scripts/check` and
stops on any failure (Codex add-on).

## `shell_lint.py`

ShellCheck on shell files: `*.sh`, `*.bash`, and files whose first line is a `sh`, `bash`, `dash`
or `ksh` shebang (`#!/usr/bin/env -S bash` too). `--all` (default) takes the files git lists
(tracked and untracked, not ignored), so a local run sees what CI sees; outside a git repo it walks
the tree, skipping `.git/`, `node_modules/` and `.venv/`. `--staged`, `--list`. ShellCheck has no
zsh support: `*.zsh` and zsh-shebang files get a parse-only `zsh -n` check instead (syntax
only, no lint); without zsh they print "zsh not found: skipped" (CI installs zsh when needed).
Without `shellcheck` it prints "shellcheck not found: skipped" and passes; with `--require` (CI) it
fails.

## Hook mechanics

Hooks are a convenience, not a boundary: `--no-verify` and a branch's own edits skip them; CI is
the check that reports.

**commit-msg and pre-commit** (git): `apply` installs both only in a repo with no hooks of its
own: `git config --get core.hooksPath` is empty, there is no `.githooks/` folder (or it holds only
the kit's own hooks), and the default hooks folder (`.git/hooks`) holds nothing but `*.sample`
files (setting `core.hooksPath` would switch those hooks off). Then it writes
`.githooks/commit-msg` and `.githooks/pre-commit`, makes them executable and runs
`git config core.hooksPath .githooks`:

```sh
#!/bin/sh
exec python3 docs/standards/checks/trailer_check.py --message-file "$1"
```

```sh
#!/bin/sh
exec python3 docs/standards/checks/pre_commit.py
```

Otherwise it changes nothing and prints the line to add to each existing hook (in the folder it
names):

```sh
python3 docs/standards/checks/trailer_check.py --message-file "$1" || exit 1
python3 docs/standards/checks/pre_commit.py || exit 1
```

`pre_commit.py` takes the staged file names and never runs tests or `scripts/check`. Ruff,
ShellCheck and `rules_check` read the working-tree content of those files, so with partial staging
(`git add -p`) they check what is on disk, not what is staged; only the secret scan reads the
index. Ruff (`format --check`, `check`) on staged `.py` files in python-stack projects (`ruff` on
`PATH`, else `.venv/bin/ruff`, else "ruff not found: skipped"; never `uv run`, which would sync the
project inside a commit hook); `secret_scan` on the staged diff; `shell_lint` on
staged shell files; `rules_check` only when `docs/standards/**`, `AGENTS.md` or `CLAUDE.md` is
staged; `state_check` as a warning.

`--dry-run` prints which case applies. Outside a git repo, or below the top of a work tree, it
installs nothing and says so. `core.hooksPath` is local git config: each clone sets it again
(re-run `apply`, or `git config core.hooksPath .githooks`).

**Claude Code** (project `.claude/settings.json`): `apply` merges these two `state_check` hooks in,
leaving existing hooks alone. The path filter goes in `if`, since `matcher` tests only the tool
name (A0 row 12).

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

The Codex SessionStart hook (worktrees holding `HANDOFF.md`) isn't installed by `apply`: the
claude-codex-integration skill copies `templates/hooks/codex-handoffs.sh` and merges its entry.

**CI** (`templates/ci/rules-check.yml`, job `rules-check`): no path filter. It takes
`docs/standards/checks/` and the manifest from a trusted base commit: on a pull request, the PR's
base; on a push to the default branch, the commit before the push (`github.event.before`), never
the pushed commit. A forced push to the default branch (GitHub's `forced` flag, or a `before`
missing from the fetched history or not an ancestor of the pushed commit) fails with a message. A
push to any other branch or tag, forced or not, uses its merge-base with the default branch: the
branch's own earlier push is not trusted (F1-1). The push that creates the default branch has only
itself, so that one run checks the commit against its own manifest and prints "first push: checked
against its own manifest only (no earlier commit)". No merge-base fails. Then it runs
`trailer_check`, `rules_check` (with `--base` set to the same commit) and `shell_lint --all
--require` (ShellCheck preinstalled on the runner: unverified until A4; if missing, the step
fails). Detection only: the workflow that runs is the pushed commit's own copy, so a branch can
edit it. That includes a direct push to the default branch (GitHub Free, `--no-pr`): one that
edits `.github/workflows/rules-check.yml` to compare with itself passes, and every later push
inherits the edit. Only review of `.github/**` changes catches that. `apply` never replaces an
existing workflow; when it differs from the kit's, `apply` says so, and the kit's copy goes in in
a separate PR.

## `bin/gate-status` (high-stakes)

Posts the `local-gate` commit status. Always run the base branch's copy (the high-stakes block
gives the same command):

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
check run has the same name (check runs filtered by name, statuses 100 per page). It refuses
`--context rules-check`, and `--base` must be `origin/<the PR's base branch>` from `gh pr view`; it
always fetches that remote first, and the script and list paths are fixed (no option changes
them). Binaries are found by their bytes, whatever `.gitattributes` says.
