# Checks

This page describes the three checks, the hook helpers (`secret_scan`, `shell_lint`,
`pre_commit`), how they're wired, and the enforcement paths the merge check names.

The scripts use the Python standard library only and run on Python 3.12 or later, managed by uv.
The kit's `scripts/check` runs the tests on 3.12, and `scripts/check --full` and the kit's own
automatic checks on GitHub also run them on 3.13. Each script starts with a short POSIX `sh`
section. When you run `sh <script>`, it looks for uv on `PATH`, then in `~/.local/bin`,
`~/.cargo/bin`, `/opt/homebrew/bin` and `/usr/local/bin`, because desktop git apps may not pass
your shell's `PATH`. Set `DEV_AI_STANDARDS_NO_UV_SEARCH=1` to skip those folders. If uv is
missing, the script prints "uv is required: brew install uv (or see
https://docs.astral.sh/uv/getting-started/installation/)" and exits 1. Otherwise it unsets
`UV_PYTHON`, which would override the version, and runs the file with `uv run --script`, whose
inline metadata asks for Python 3.12 or later. uv needs a writable cache folder (`~/.cache/uv`, or
set `UV_CACHE_DIR`); without one the hook fails. The same file is also plain Python, so
`python <script>` works where Python 3.12 is already set up, as on GitHub's runners. Each script
has `--help`. In a project, the scripts live in `docs/standards/checks/`, which the kit owns and
`apply` copies.

## Enforcement paths

The merge check names every changed path below. A change to one of them never counts as docs
only, whatever a project's docs-only list says. On a `codex/*` branch, any change to one of them
fails the merge check.

- `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `CLAUDE.local.md`, `CODEOWNERS` and
  `.gitattributes` count at any depth. Claude Code and Codex read nested instruction files, and a
  nested `.gitattributes` changes how git sees files.
- Anything under a `.claude/`, `.codex/`, `.agents/` or `.githooks/` folder counts at any depth,
  and so does every script a hook calls.
- `checks/**`, `bin/**`, `scripts/check` and `scripts/setup` count.
- `.github/**` counts, including the workflows and the docs-only list.
- `docs/standards/**` counts.

The merge check also fails when a workflow job's `name:` equals a required status check
(`rules-check`, and `local-gate` with a local gate). On `codex/*` branches it also fails on a
change to a plan's Decisions or approval lines.

## `trailer_check.py`

Each commit must have exactly one co-author trailer, and it must be one of these:

```text
Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
```

The trailer must sit in the message's last paragraph. Any other `Co-Authored-By:` line, such as
another name, a model name or a second trailer, fails.

| Mode | Use |
|---|---|
| `--message-file <file>` | `commit-msg` hook; `#` comment lines and text below the scissors line are ignored |
| `--commit <sha>` | one commit |
| `--range A..B` | every commit in `A..B` (GitHub's checks on a pull request: base..head) |
| `--push BEFORE AFTER --ref <ref> [--base-ref origin/main]` | GitHub's checks on a push: only the commits the push adds |

On a push, the check reads the commits in `before..after`. For a new branch (`before` is all
zeros), it starts from the branch's merge-base with the base branch. For an orphan branch, it starts
from the branch's root. A deletion (`after` is all zeros) checks nothing. A push to the base branch
whose `before` isn't in the fetched history is a force push, and it fails, because the commits it
adds can't be told apart.

Three kinds of commit are exempt, and only in the commit modes:

- Dependabot commits are exempt when the GitHub author login is `dependabot[bot]` and the signature
  is verified.
- GitHub's merge commits are exempt when they have more than one parent, the committer login is
  `web-flow` and the signature is verified. This exemption is unproven. An unsigned commit that
  only claims GitHub's name fails.
- The launcher's root commit is exempt when its subject is `new-claude-project: initial commit`, it
  has no parents, and it arrives on the push that creates the base branch (`before` is all zeros,
  `--ref refs/heads/main`). The same subject on a later commit or on an orphan branch's root fails.

The check reads logins and signatures from the GitHub API (`--github-repo OWNER/REPO`, with a
token in `GITHUB_TOKEN`) or from a JSON file (`--meta`, for tests). Without either, no Dependabot or
`web-flow` exemption applies.

## `rules_check.py`

Run it as `rules_check.py [--base REF] [--manifest FILE] [--budget BYTES] [--branch NAME]
[--default-branch NAME] [<dir>]`. It fails in these cases:

- `CLAUDE.md` has no line that is exactly `@AGENTS.md` outside fenced code and HTML comments.
  Claude Code ignores imports inside those.
- `AGENTS.md` is over the size budget. The default is 24 KiB, well under Codex's 32 KiB limit for
  all its instruction files together. Each project sets one number with `--budget` in the workflow.
- A backticked path in the `Read` column of a read-before table doesn't exist, or a kit row is
  missing. Skill names and URLs are skipped. The kit rows are honesty, outside sources and this
  file, plus diff-review in high-stakes projects; the trusted manifest selects them, and `apply`
  adds them.
- A kit file, or a kit block in `AGENTS.md` or `CLAUDE.md`, differs from the trusted manifest, is
  missing, or isn't listed, unless the branch is a kit upgrade (see below). Any file under
  `docs/standards/` that the manifest doesn't name counts as not listed.
- `## Overrides` appears more than once, or a line in it isn't `- <block name>: <text>` with a
  known block name.
- A file under `.githooks/`, or `scripts/setup`, that exists in the base commit is deleted, emptied
  or no longer executable, or it no longer mentions `docs/standards/checks/` when the base's copy
  did. The base must have mode 100755, since git silently skips a hook that isn't executable, and a
  newcomer's `scripts/setup` needs the checks.
- In a change to the default branch, a number placeholder (`ADR-NEW`, `OD-NEW`, `P-NEW`, or
  `OD-NEW-1` and so on) is left where a real number belongs. The message says "assign numbers
  before merging". The details follow this list.

A change to the default branch is a pull request whose base is the default branch
(`GITHUB_BASE_REF`), a push to it, or, on your machine, `--branch` or the current branch being it.
Any other branch passes. The check finds the default branch from `--default-branch`, else, in
GitHub Actions, the workflow's `DEFAULT_BRANCH` (`github.event.repository.default_branch`), else
`origin/HEAD`, else whichever of `main` and `master` exists. If it can't find one, it skips the
check and prints a line saying so. It scans tracked files only. It looks at file and folder names
under `docs/adr/` and `planning-docs/` (`NEW-slug.md`, `P-NEW-slug.md`), the first line of each
Markdown file there (the ADR title or the plan header), and decision definition lines in any
Markdown file (`- OD-NEW: ...`, from the planning add-on). It never scans `docs/standards/**`, the
fixed rule files, kit blocks, code spans, fenced code, HTML comments, or text that only mentions a
placeholder.

The check warns, without failing, when the change edits the `## People` section of `AGENTS.md`. It
prints "People changed: needs the owner's approval (merge by the owner listed on <default>)", and
in GitHub Actions it also adds the warning to the run as an annotation. People counts only from the
default branch. `rules_check.py --people` prints the Owner and Approvers from
`origin/<default>:AGENTS.md`, else from the local `<default>`, and never from the working tree.
Agents and tools read People that way.

The check always prints the overrides it found. The trusted manifest is `--manifest FILE` (on
GitHub, the base branch's copy), else the one on `--base REF`, else `origin/main`, then `main`. The
check reads the working copy only when no base branch exists or the base has no manifest yet (the
first adoption), and it says so. A branch's edit to its own manifest therefore changes nothing,
except in a kit upgrade.

**Kit upgrades.** A branch that re-runs `apply` for a new kit version changes kit text and the
manifest together. `rules_check` then checks against the branch's own manifest, instead of the
base's, only when all of these hold:

- Every changed path is in a fixed set that is never read from any manifest: `docs/standards/**`
  (the manifest included), `.claude/rules/state-file.md`, `.claude/rules/user-docs.md`,
  `AGENTS.md` and `CLAUDE.md`. In the last two, only text inside kit blocks and the `Standards:`
  line may change. When a kit release changes how its scripts or hooks start (the interpreter or
  launcher), the upgrade may also change files directly in `.githooks/` and `scripts/check`, so
  commits keep working between the two pull requests. Those paths pass only inside a valid
  upgrade, so only when the `Standards:` version increases.
- The `Standards:` line names a strictly newer version than the base's, in semantic-version order.
- The branch's kit files and blocks match the branch's manifest.

The changed paths are those between the merge-base with the base ref (`--base`, else
`origin/main`, then `main`) and the working tree, untracked files included. On GitHub, the workflow
passes the pull request's base as `--base`. Any branch whose manifest or version differs from the
base's goes through this rule, even if its kit text still matches the base manifest, so a manifest
edit outside an upgrade fails. A branch that misses the rule fails with the reason, for example
"kit upgrade PRs may change only docs/standards/** ... (also changed: ...)", plus the usual
findings against the base manifest. The rest of what `apply` writes on an upgrade therefore goes in
its own pull request, as does the changelog line. That rest is the `.gitignore` lines,
`.claude/settings.json`, new read-before rows, and the hooks and `scripts/check` when the release
didn't change how scripts start.

`dev-ai-standards drift` applies the same rule. Within the rule, a pure upgrade may rewrite or
remove any kit file or block, the checks included, and nothing ties it to a real kit release. The
pull request review compares the kit diff with the kit's `CHANGELOG.md`.

Only `apply` writes the manifest. It has one line per kit file or block, in one of these forms:

- `<sha256 hex>  docs/standards/<path>`
- `<sha256 hex>  .claude/rules/state-file.md` or `<sha256 hex>  .claude/rules/user-docs.md`. These
  are two fixed names, because Claude Code reads rules only from `.claude/rules/`.
- `<sha256 hex>  <AGENTS.md|CLAUDE.md>#<block>`

A block's fingerprint covers the exact text between its two markers, without the markers. Any
other key fails the check and stops `apply`. That includes `..`, an absolute path, a backslash,
another path outside `docs/standards/`, and an unknown block.

## `state_check.py`

This check comes with the state-file add-on. It only warns, and only about sizes. It warns when the
file is over 8 KiB (8,192 bytes), when a line is over 300 characters, when Next steps or Open
questions has more than 10 entries, and when Recent progress has more than 16. Entries are
top-level `- ` lines under each `## ` heading. The check never fails.

| Mode | Reports | Exit |
|---|---|---|
| `state_check.py [<file>]` | the whole file (default: `CLAUDE-STATE.md` in the main checkout, found with `git rev-parse --git-common-dir`) | 0 |
| `--hook session-start` | the whole file, on stdout | 0 |
| `--hook post-tool-use` | only that Edit or Write: long lines inside the edit, caps of the sections it touched, the file size if the edit grew it | 2 with warnings on stderr (shows them to Claude; the edit already happened), else 0 |

## `secret_scan.py`

The secret scan looks for the shapes of credentials in the lines a change adds: AWS access key
IDs, private key blocks, and GitHub, Anthropic, OpenAI-style and Slack tokens. It is a tripwire,
not a guarantee. It prints the file, line number and kind of each hit, never any line content. It
reads the diff hunk by hunk. A line starting with `+++ ` is a file header only outside a hunk;
inside a hunk, every line starting with `+` is an added line, so `++ x` adds `+ x`. The staged diff
uses fixed `a/` and `b/` prefixes whatever your git config says. `--staged` (the default) scans the
staged diff, and `--diff-file F` scans a saved diff. The scan exits 1 on a hit. With the Codex
add-on, Claude runs it and `scripts/check` before a hooks-off commit of Codex work and stops on any
failure.

## `shell_lint.py`

This helper runs ShellCheck on shell files: `*.sh`, `*.bash`, and files whose first line is a
`sh`, `bash`, `dash` or `ksh` shebang (`#!/usr/bin/env -S bash` counts too). `--all`, the default,
takes the files git lists (tracked and untracked, but not ignored), so a run on your machine sees
what GitHub's checks see. Outside a git repo, it walks the folder tree and skips `.git/`,
`node_modules/` and `.venv/`. `--staged` checks only staged files, and `--list` prints the files it
would check. ShellCheck doesn't support zsh, so `*.zsh` files and files with a zsh shebang get a
syntax-only `zsh -n` check instead. Without zsh, the helper prints "zsh not found: skipped" for
them; GitHub's checks install zsh when needed. Without `shellcheck`, it prints "shellcheck not
found: skipped" and passes. With `--require`, which GitHub's checks use, it fails instead.

## Hook mechanics

Hooks are a convenience, not a boundary. `--no-verify` and a branch's own edits skip them. GitHub's
automatic checks are the checks that report.

**commit-msg and pre-commit (git).** `apply` installs both only in a repo with no hooks of its own.
That means `git config --get core.hooksPath` is empty, there is no `.githooks/` folder (or it holds
only the kit's own hooks), and the default hooks folder (`.git/hooks`) holds nothing but `*.sample`
files. Setting `core.hooksPath` would switch any other hooks off. In that case `apply` writes
`.githooks/commit-msg` and `.githooks/pre-commit`, makes them executable and runs
`git config core.hooksPath .githooks`:

```sh
#!/bin/sh
exec sh docs/standards/checks/trailer_check.py --message-file "$1"
```

```sh
#!/bin/sh
exec sh docs/standards/checks/pre_commit.py
```

Otherwise it changes nothing and prints the line to add to each existing hook, in the folder it
names:

```sh
sh docs/standards/checks/trailer_check.py --message-file "$1" || exit 1
sh docs/standards/checks/pre_commit.py || exit 1
```

`pre_commit.py` takes the staged file names and never runs tests or `scripts/check`. Ruff,
ShellCheck and `rules_check` read the working-tree content of those files. With partial staging
(`git add -p`), they therefore check what is on disk, not what is staged; only the secret scan
reads the staged content. The hook runs these checks:

- In python-stack projects, it runs Ruff (`format --check` and `check`) on staged `.py` files. It
  uses `ruff` on `PATH`, else `.venv/bin/ruff`, else it prints "ruff not found: skipped". It never
  uses `uv run`, which would sync the project inside a commit hook.
- It runs `secret_scan` on the staged diff.
- It runs `shell_lint` on staged shell files.
- It runs `rules_check` only when `docs/standards/**`, `AGENTS.md` or `CLAUDE.md` is staged.
- It runs `state_check` as a warning.

`apply` rewrites hooks that an earlier kit version wrote (`exec python3 ...`). It reports a
`python3 docs/standards/checks/` line in a project's own hook, since the checks now need
Python 3.12 through uv. `--dry-run` prints which case applies. Outside a git repo, or below the top
of a work tree, `apply` installs nothing and says so. `core.hooksPath` is local git config, so each
clone sets it again with `scripts/setup`. `apply` writes `scripts/setup` into every project once,
and the project owns it afterwards. It runs `docs/standards/bin/bootstrap`, which checks for the
Xcode Command Line Tools, git and uv. Then it sets `core.hooksPath .githooks`, but only when
`.githooks/` holds the kit's hooks and the clone has no `core.hooksPath` and no hooks of its own in
`.git/hooks`.

**Claude Code (the project's `.claude/settings.json`).** `apply` merges these two `state_check`
hooks in and leaves existing hooks alone. It removes the `python3` form of these two commands that
earlier kit versions wrote. The path filter goes in `if`, because `matcher` tests only the tool
name.

```json
{
  "hooks": {
    "PostToolUse": [
      {"matcher": "Edit|Write", "hooks": [{"type": "command", "if": "Edit(**/CLAUDE-STATE.md)",
        "command": "sh \"$CLAUDE_PROJECT_DIR\"/docs/standards/checks/state_check.py --hook post-tool-use"}]}
    ],
    "SessionStart": [
      {"hooks": [{"type": "command",
        "command": "sh \"$CLAUDE_PROJECT_DIR\"/docs/standards/checks/state_check.py --hook session-start"}]}
    ]
  }
}
```

The exact `if` form that covers Write as well as Edit is unproven. The script itself ignores any
file not named `CLAUDE-STATE.md`, so a broader filter does no harm.

`apply` doesn't install the Codex SessionStart hook, which lists worktrees that hold `HANDOFF.md`.
The claude-codex-integration skill copies `templates/hooks/codex-handoffs.sh` and merges its entry.

**GitHub's automatic checks (`templates/ci/rules-check.yml`, job `rules-check`).** The workflow has
no path filter. It takes `docs/standards/checks/` and the manifest from a trusted base commit. On a
pull request, that is the pull request's base. On a push to the default branch, it is the commit
before the push (`github.event.before`), never the pushed commit. A forced push to the default
branch fails with a message. The workflow detects one from GitHub's `forced` flag, or from a
`before` that is missing from the fetched history or isn't an ancestor of the pushed commit. A push
to any other branch or tag, forced or not, uses its merge-base with the default branch, because the
branch's own earlier push is not trusted. The push that creates the default branch has only
itself, so that one run checks the commit against its own manifest and prints "first push: checked
against its own manifest only (no earlier commit)". A push with no merge-base fails. The workflow
then runs `trailer_check`, `rules_check` (with `--base` set to the same commit) and
`shell_lint --all --require`. ShellCheck is expected to be preinstalled on GitHub's runner; this is
unverified, and if it is missing, the step fails.

The workflow only detects problems. The copy that runs is the pushed commit's own, so a branch can
edit it. That includes a direct push to the default branch (on GitHub Free, or with `--no-pr`): a
push that edits `.github/workflows/rules-check.yml` to compare with itself passes, and every later
push inherits the edit. Only a review of `.github/**` changes catches that. `apply` never replaces
an existing workflow. When the workflow differs from the kit's, `apply` says so, and the kit's copy
goes in through a separate pull request.

## `bin/gate-status` (high-stakes)

This script posts the `local-gate` commit status. Always run the base branch's copy; the
high-stakes block gives the same command:

```sh
git fetch origin
d=$(mktemp -d)
git show origin/main:docs/standards/bin/gate-status > "$d/gate-status"
uv run --no-project --python 3.12 python "$d/gate-status" --check
```

Always use `uv run ... python`, never `sh`. The base copy may predate the `sh` start section, and
`sh` would run its Python lines as shell commands. `--no-project` keeps uv from syncing the
project's own environment. The command uses `mktemp -d` because `$TMPDIR` is unset on Linux.

The script also re-runs the base copy itself when the copy it was started from differs. That
guards against a stale or edited copy, not against a hostile one, which is why the command above
comes first. The script reads the docs-only list (`.github/docs-only-paths`, project-owned path
prefixes) only from the base branch. It checks both sides of every rename. Copies, binaries,
submodules, symlinks and enforcement paths never count as docs only. `--passed N --skipped 0`
refuses a dirty tree, a `HEAD` other than the pull request's head, or any skip. It can't prove the
run happened, so post only after the real full run. `--verify --operator <login>` checks that the
status was created by that GitHub login and that no check run has the same name. It filters check
runs by name and reads statuses 100 per page. The script refuses `--context rules-check`, and
`--base` must be `origin/<the PR's base branch>` from `gh pr view`. It always fetches that remote
first, and the script and list paths are fixed; no option changes them. It finds binaries by their
bytes, whatever `.gitattributes` says.
