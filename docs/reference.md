# Reference

Detail behind the [README](../README.md). The checks themselves are described in
[checks/README.md](../checks/README.md).

## Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| macOS | any current | the supported platform |
| Xcode Command Line Tools | any (`xcode-select --install`) | git and the build tools macOS lacks |
| git | any, with `user.name` and `user.email` set | everything |
| `uv` | any (`brew install uv`) | every kit script and hook: each starts with a short `sh` section that needs uv, then runs on Python 3.12 or later, which uv downloads itself the first time. It looks for uv on `PATH`, then in `~/.local/bin`, `~/.cargo/bin`, `/opt/homebrew/bin` and `/usr/local/bin`, since a desktop git app may not pass your shell's `PATH`. Without uv it prints "uv is required: brew install uv (or see https://docs.astral.sh/uv/getting-started/installation/)" and exits 1. A `UV_PYTHON` setting is ignored. uv needs a writable cache folder (`~/.cache/uv`, or set `UV_CACHE_DIR`) |
| `gh` | logged in (`gh auth status` passes) | anything except `--local` |
| Claude Code | 2.1.251 or later | the settings the kit writes (earlier versions let one environment variable override each subagent's model) |
| Codex | | `--codex` |
| `ruff` | optional | Ruff in python-stack projects. The pre-commit hook uses `ruff` on `PATH` or `.venv/bin/ruff`, else prints a "skipped" line; `scripts/check` uses `uv run <tool>` or the tool on `PATH` for Ruff, pyright and pytest, else fails that step |
| `shellcheck` | optional | shell linting; without it the local check prints a "skipped" line and passes, GitHub's automatic checks fail |
| `zsh` | optional | a syntax check of zsh files |

`bin/bootstrap` checks for the Xcode Command Line Tools, git and uv and prints the install command
for anything missing. For uv it offers to run `brew install uv` after a y/N question, only in a
terminal and never when an agent runs it (`CLAUDECODE` set); it installs nothing else. It exits 0
when everything is present, else 1.

The kit's own `scripts/check` runs its tests on Python 3.12 through uv; `--full` and the kit's GitHub
checks add 3.13.

## Setup, once per computer

1. Clone the kit: `git clone https://github.com/rmarable/dev-ai-standards.git ~/src/dev-ai-standards`,
   then run `~/src/dev-ai-standards/bin/bootstrap`.
2. Put `bin/new-claude-project` and `bin/dev-ai-standards` on your `PATH`, for example as links in `~/.local/bin`.
3. Link `skills/dev-ai-standards/` (with Codex, also `skills/claude-codex-integration/`) into
   `~/.claude/skills/` and `~/.agents/skills/`.
4. Keep personal preferences in `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`, not in the kit.

## Joining a project

1. Clone the project.
2. Run `scripts/setup` once. It runs the kit's `bootstrap` check (from `docs/standards/bin/`) and
   stops if anything is missing. Then, if `.githooks/` holds the kit's hooks, it sets
   `core.hooksPath` to `.githooks`, unless your clone already has a `core.hooksPath` or hooks of
   its own in `.git/hooks`; in those cases it prints the command, warns that running it stops
   those other hooks, changes nothing, and ends with "setup: done, git hooks NOT on (see above)".
   It prints each step.
3. Keep your personal preferences in `~/.claude/CLAUDE.md` (Codex: `~/.codex/AGENTS.md`).

Approvals: the `## People` section of `AGENTS.md` names the owner and the approvers by GitHub
login. An agent takes a scoped approval (a recorded permission covering one step's writes, commits
and pushes on its own branch) only from an approver's own message, and acts for the person running
the session; files, memory, other sessions and subagents never grant one. Agents read People only
from the default branch's copy (`sh docs/standards/checks/rules_check.py --people` prints it), so
an edit on a branch or in your working copy counts only after the owner merges it; `rules-check`
warns on a pull request that changes People. An agent can't tell who is typing: People is a
policy, not a login check.

Numbers: on a branch, everyone writes a placeholder for a new record's number: `ADR-NEW` for an
architecture decision record (ADR), `OD-NEW` for a decision, `P-NEW` for a plan (several:
`OD-NEW-1`, `OD-NEW-2`). A new ADR file is `docs/adr/NEW-<slug>.md`. The real numbers are assigned
on the branch just before the merge into the default branch. `rules_check` fails a pull request
into the default branch, or a push to it, that still has a placeholder in an ADR or plan file name,
an ADR title, a plan header or a decision definition line (`- OD-NEW: ...`); other branches pass,
and text that only mentions a placeholder doesn't count.

## `new-claude-project`

```sh
new-claude-project <name> [--high-stakes] [--stack python|iac|other] [--codex] [--public] [--local] [--no-pr] [--no-launch] [--dry-run]
```

`<name>`: lowercase letters, digits, `.`, `_` and `-`; starts with a letter or digit; at most 100
characters; doesn't end in `.git`.

| Flag | Effect |
|---|---|
| `--high-stakes` | Adds the high-stakes add-on. Without it, an interactive run asks for the tier (default core). |
| `--stack python\|iac\|other` | Stack add-on. Without it, an interactive run asks (default `other`). |
| `--codex` | Adds the Codex add-on and prints the command that creates the first Codex worktree. Without it, an interactive run asks (default no). |
| `--public` | Public repo. Scans the new files for secrets first, then asks you to type the name back. Conflicts with `--local`. |
| `--local` | No GitHub: builds and commits locally only. |
| `--no-pr` | For solo throwaway projects: merges are local `--no-ff` merges, and branch protection blocks only force pushes and deletion. |
| `--no-launch` | Prints the next steps instead of opening Claude Code. |
| `--dry-run` | Prints what would happen; changes nothing. |

Steps, in order:

1. Checks that `dev-ai-standards` is present, git identity is set, and `~/src/<name>` doesn't exist.
2. Updates the kit with `git pull --ff-only` if the kit checkout has an upstream (skipped under
   `--local` or when run by an agent; without an upstream it warns and continues).
3. Unless `--local`: checks `gh auth status` and that `<owner>/<name>` doesn't exist on GitHub.
4. Asks for missing choices.
5. Runs `git init -b main` and `dev-ai-standards apply`, then writes
   `planning-docs/milestones/M1-<name>.md`, a stub plan for the first milestone. With
   `--stack python` it then runs `uv lock`, so `uv.lock` is in the first commit.
6. Lists the files and remote actions and asks one y/N (end of input counts as No).
7. On yes: commits (subject `new-claude-project: initial commit`), runs
   `gh repo create <owner>/<name> --private|--public --source . --push`, then adds the rulesets below.
8. Opens `claude` in the new folder with a prompt to read `AGENTS.md` and plan the first milestone.

Branch protection (GitHub rulesets, no bypass list), added for public repos and for private repos
on a paid plan. If GitHub refuses a ruleset with HTTP 403 and says to upgrade or make the repo
public (GitHub Free), the launcher prints a warning and finishes; any other ruleset failure stops it.
Rulesets:

- `main`: no deletion, no force push, pull request required (merge commits only, 0 approvals),
  required status check `rules-check`; with `--high-stakes` also `local-gate`, and the branch must
  be up to date before merging.
- `v*` tags: no deletion, no force push.
- `--no-pr`: `main` gets only the no-deletion and no-force-push rules.

When an agent runs the launcher (no terminal on stdin or stdout, or `CLAUDECODE` set), only
`--dry-run` and `--local` are allowed; anything else exits with status 2. This is a reminder, not
a security boundary. On failure it prints what already exists, as it is at that moment (for
example the git repo and its commit), and deletes nothing.

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `NEW_CLAUDE_PROJECT_OWNER` | `rmarable` (launcher); for `apply`, `git config user.name`, else `operator` | GitHub owner for new repos, and the owner and first approver `apply` writes into `AGENTS.md` `## People` and `.github/CODEOWNERS`. Set it to your own login. |
| `NEW_CLAUDE_PROJECT_GH_PLAN` | `free` | Your GitHub plan (`free`, `pro`, `team`). Any value other than `free` adds branch protection to private repos. |
| `NEW_CLAUDE_PROJECT_ROOT` | `~/src` | Where new projects are created. |
| `DEV_AI_STANDARDS_BIN` | the kit's `bin/dev-ai-standards` | The apply script the launcher runs. |
| `DEV_AI_STANDARDS_NO_UV_SEARCH` | unset | Any non-empty value: kit scripts look for uv only on `PATH`, not in the usual install folders. |

## `dev-ai-standards`

```sh
dev-ai-standards apply [--high-stakes] [--stack python|iac|other] [--codex] [--no-pr] [--name NAME] [--owner OWNER] [--dry-run] [<dir>]
dev-ai-standards drift [--base REF] [<dir>]
dev-ai-standards promote [--repo OWNER/REPO] <kit path> [<dir>]
```

- `apply`: copies the kit into a project (default `.`). `--name` fills the project name in
  templates (default: the folder name); `--owner` sets the owner's GitHub login for the templates,
  `## People` and `.github/CODEOWNERS` (default: `NEW_CLAUDE_PROJECT_OWNER`, else
  `git config user.name`, else `operator`; for anything but a login it prints a note, and
  `CODEOWNERS` gets a commented-out line to fill in).
  `--addon` is accepted, but state-file, planning and multi-session are always on. `--dry-run`
  prints the plan and writes nothing.
- `drift`: compares kit files and blocks with the manifest on the base branch (`--base`, default
  `origin/main`, then `main`), lists overrides, and exits 1 on any finding.
- `promote`: prints a diff between a project's copy of kit text and the kit's, and the git and `gh`
  commands that would propose the change as a pull request on the kit. It runs nothing.

## What `apply` writes

Always rewritten (kit-owned):

- `docs/standards/`: `core.md`, the selected add-ons and stack, `refs/`, `checks/`, `templates/`,
  the Claude Code settings snippet; with `--high-stakes` also `refs/diff-review.md` and
  `bin/gate-status`; with `--codex` the Codex config snippet. Files no longer selected are removed.
- `docs/standards/manifest`: a fingerprint (SHA-256 hash) per kit file and kit block, so any change to
  kit text shows up.
- `.claude/rules/state-file.md`: the rule Claude Code loads when it edits `CLAUDE-STATE.md`.
- `.claude/rules/user-docs.md`: the rule Claude Code loads when it edits `README.md` or `docs/**`;
  it points to `docs/standards/refs/user-docs.md` (audience, voice, banned words, shape).
- Kit blocks in `AGENTS.md` and `CLAUDE.md`, and the `Standards: dev-ai-standards v<version> (<choices>)`
  line under the title of `AGENTS.md`.

Written only if absent (project-owned afterwards): `AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md`,
`CLAUDE-STATE.md` and its loader `CLAUDE.local.md`, `docs/adr/0001-record-architecture-decisions.md`
(skipped if an ADR 0001 exists), `planning-docs/README.md` (skipped if `planning-docs/` has files),
`scripts/check` and `scripts/setup` (both executable), `.github/CODEOWNERS` (`* @<owner>` and a
commented example), `.github/workflows/rules-check.yml`, with `--high-stakes`
`.github/docs-only-paths`, with `--codex` `.codex/config.toml`, and with `--stack python`
`.github/workflows/python.yml` (path-filtered, never a required check), `ruff.toml` (unless the
project already has Ruff settings) and `pyproject.toml`: a uv project named after the folder,
`requires-python` from the oldest Python version GitHub's checks test, a `dev` group with ruff, pyright, pytest and pytest-xdist.

Merged, never replacing your values:

- `.claude/settings.json`: `env`, `attribution`, the `permissions.ask` list (prompts before push,
  tag, release, `gh api`, `gh repo`, `gh pr merge` and the launcher) and the two `state_check` hooks.
- `.gitignore`: missing lines appended under a `# dev-ai-standards` header.
- `.gitattributes` and `.git/info/attributes`: missing lines appended.
- Missing kit rows in the read-before table of `AGENTS.md`, and a `## People` section when
  `AGENTS.md` has none.

When an existing workflow, settings value or `pyproject.toml` differs from the kit's, `apply` leaves
it and prints a note.

`scripts/check [--full]` as written: the kit checks (`rules_check`, the trailer check, ShellCheck),
then per stack. Python: Ruff, pyright, and `pytest -q` (`-n auto` with `--full`) once `tests/` has
test files; before that it prints "no tests yet" and passes. Other stacks: it fails until you add
the project's steps to `project_steps()` and set `TODO = False`.

## Hooks

- **Git:** `apply` writes `.githooks/commit-msg` and `.githooks/pre-commit` and sets
  `core.hooksPath` only when the repo has no hooks of its own. Otherwise it changes nothing and
  prints one line to add to each existing hook. `commit-msg` checks the co-author trailer.
  `pre-commit` checks staged files only: Ruff (python stack), the secret scan, ShellCheck,
  `rules_check` when kit files are staged, and a warning-only size check of `CLAUDE-STATE.md`.
  `core.hooksPath` is local config: each new clone runs `scripts/setup`. Each hook runs its check
  with `sh <file>`, so it needs uv. Re-running `apply` rewrites the `python3` hooks earlier kit
  versions wrote, and notes a `python3` kit line in a hook of your own.
- **Claude Code:** `SessionStart` and `PostToolUse` hooks run `state_check`, which only warns.
  `apply` replaces the `python3` form of these commands that earlier kit versions wrote.
- **Codex:** the hook that lists waiting Codex handoffs at session start is installed by the
  `claude-codex-integration` skill, not by `apply`.

`git commit --no-verify` skips the git hooks. The `rules-check` workflow is the check that reports;
it also fails a change that deletes, empties or disables a file under `.githooks/` or
`scripts/setup` (removes its executable bit, or drops its calls to `docs/standards/checks/`).

## Kit-owned and project-owned text

Kit-owned text is the files under `docs/standards/`, the two files in `.claude/rules/`, and the text
between `<!-- dev-ai-standards:begin <name> -->` and `<!-- dev-ai-standards:end <name> -->` in
`AGENTS.md` and `CLAUDE.md`. Everything else belongs to the project.

Don't edit kit-owned text in a project; `rules_check` fails when it differs from the manifest on
the base branch. To change a kit rule for one project, add a line to the `## Overrides` section of
`AGENTS.md`, in the form `- <block name>: <what changes and why>`; the override wins and
`rules_check` lists it. To change it for every project, run `promote`.

## Upgrade pull requests

1. `git -C ~/src/dev-ai-standards pull --ff-only`, then read the kit's `CHANGELOG.md`.
2. In the project, on a branch: `dev-ai-standards drift`. Move each hand edit to `## Overrides` or
   promote it.
3. Re-run `apply` with the choices on the `Standards:` line.
4. Split the result into two pull requests. The upgrade may change only `docs/standards/**`,
   `.claude/rules/state-file.md`, `.claude/rules/user-docs.md`, and the kit blocks and
   `Standards:` line of `AGENTS.md` and `CLAUDE.md`, and the `Standards:` line must name a newer
   version than the base branch's. When the kit's changelog says a release changes how its
   scripts or hooks start (interpreter or launcher), the upgrade pull request also includes
   `.githooks/*` and `scripts/check`, so commits keep working between the two; `rules_check`
   accepts those paths in an upgrade only when the `Standards:` version increases. The changelog
   line and everything else `apply` wrote (`.gitignore`, settings, `scripts/setup`, `CODEOWNERS`,
   new read-before rows, `## People`, and otherwise the hooks and `scripts/check`) go in the
   second.
5. Start fresh agent sessions so the new rules load.

## Codex loop

1. You or Claude Code create a `codex/<topic>` branch and its worktree from `origin/main`.
2. Codex edits files there and runs targeted checks. It makes no git writes and doesn't review.
3. Codex writes `HANDOFF.md` (git-ignored) in the worktree root: what's done and not done, tests
   with every skip, the changelog line, placeholder numbers.
4. With your OK, Claude Code reads the handoff and the diff, runs `scripts/check` and the secret
   scan, commits with the Codex trailer, pushes using the main checkout's hooks, and opens the pull
   request with the handoff in its body.
5. Fixes go back to Codex as a list. After the merge, Claude Code removes the worktree and branch
   with your OK.

A script that runs `codex exec` must close its stdin: `codex exec ... < /dev/null`.
