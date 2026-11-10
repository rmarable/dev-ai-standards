# Reference

Detail behind the [README](../README.md). The checks themselves are described in
[checks/README.md](../checks/README.md).

## Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| macOS | any current | the supported platform |
| `python3` | 3.9 or later (the stock `/usr/bin/python3` works) | every kit script; standard library only |
| git | any, with `user.name` and `user.email` set | everything |
| `gh` | logged in (`gh auth status` passes) | anything except `--local` |
| Claude Code | 2.1.251 or later | the settings the kit writes (earlier versions let one environment variable override each subagent's model) |
| Codex | | `--codex` |
| `uv` | python stack | `uv lock` before the first commit (without uv the launcher warns, and CI's `uv sync --locked` fails until you run `uv lock`); CI installs it itself |
| `uv` or `ruff` | optional | Ruff in python-stack projects. The pre-commit hook uses `ruff` on `PATH` or `.venv/bin/ruff`, else prints a "skipped" line; `scripts/check` uses `uv run <tool>` or the tool on `PATH` for Ruff, pyright and pytest, else fails that step |
| `shellcheck` | optional | shell linting; without it the local check prints a "skipped" line and passes, CI fails |
| `zsh` | optional | a syntax check of zsh files |

The kit's own CI runs its tests on Python 3.9 and 3.12.

## Setup, once per computer

1. Clone the kit: `git clone https://github.com/rmarable/dev-ai-standards.git ~/src/dev-ai-standards`.
2. Put `bin/new-claude-project` and `bin/dev-ai-standards` on your `PATH`, for example as links in `~/.local/bin`.
3. Link `skills/dev-ai-standards/` (with Codex, also `skills/claude-codex-integration/`) into
   `~/.claude/skills/` and `~/.agents/skills/`.
4. Keep personal preferences in `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`, not in the kit.

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
| `NEW_CLAUDE_PROJECT_OWNER` | `rmarable` | GitHub owner for new repos. Set it to your own login. |
| `NEW_CLAUDE_PROJECT_GH_PLAN` | `free` | Your GitHub plan (`free`, `pro`, `team`). Any value other than `free` adds branch protection to private repos. |
| `NEW_CLAUDE_PROJECT_ROOT` | `~/src` | Where new projects are created. |
| `DEV_AI_STANDARDS_BIN` | the kit's `bin/dev-ai-standards` | The apply script the launcher runs. |

## `dev-ai-standards`

```sh
dev-ai-standards apply [--high-stakes] [--stack python|iac|other] [--codex] [--no-pr] [--name NAME] [--owner OWNER] [--dry-run] [<dir>]
dev-ai-standards drift [--base REF] [<dir>]
dev-ai-standards promote [--repo OWNER/REPO] <kit path> [<dir>]
```

- `apply`: copies the kit into a project (default `.`). `--name` fills the project name in
  templates (default: the folder name); `--owner` fills the owner (default `operator`).
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
- `docs/standards/manifest`: a SHA-256 hash per kit file and kit block.
- `.claude/rules/state-file.md`: the rule Claude Code loads when it edits `CLAUDE-STATE.md`.
- `.claude/rules/user-docs.md`: the rule Claude Code loads when it edits `README.md` or `docs/**`;
  it points to `docs/standards/refs/user-docs.md` (audience, voice, banned words, shape).
- Kit blocks in `AGENTS.md` and `CLAUDE.md`, and the `Standards: dev-ai-standards v<version> (<choices>)`
  line under the title of `AGENTS.md`.

Written only if absent (project-owned afterwards): `AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md`,
`CLAUDE-STATE.md` and its loader `CLAUDE.local.md`, `docs/adr/0001-record-architecture-decisions.md`
(skipped if an ADR 0001 exists), `planning-docs/README.md` (skipped if `planning-docs/` has files),
`scripts/check` (executable), `.github/workflows/rules-check.yml`, with `--high-stakes`
`.github/docs-only-paths`, with `--codex` `.codex/config.toml`, and with `--stack python`
`.github/workflows/python.yml` (path-filtered, never a required check), `ruff.toml` (unless the
project already has Ruff settings) and `pyproject.toml`: a uv project named after the folder,
`requires-python` from the CI minimum, a `dev` group with ruff, pyright, pytest and pytest-xdist.

Merged, never replacing your values:

- `.claude/settings.json`: `env`, `attribution`, the `permissions.ask` list (prompts before push,
  tag, release, `gh api`, `gh repo`, `gh pr merge` and the launcher) and the two `state_check` hooks.
- `.gitignore`: missing lines appended under a `# dev-ai-standards` header.
- `.gitattributes` and `.git/info/attributes`: missing lines appended.
- Missing kit rows in the read-before table of `AGENTS.md`.

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
  `core.hooksPath` is local config: each new clone runs `apply` again or sets it by hand.
- **Claude Code:** `SessionStart` and `PostToolUse` hooks run `state_check`, which only warns.
- **Codex:** the hook that lists waiting Codex handoffs at session start is installed by the
  `claude-codex-integration` skill, not by `apply`.

`git commit --no-verify` skips the git hooks. The `rules-check` workflow is the check that reports.

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
   `.claude/rules/state-file.md`, `.claude/rules/user-docs.md`, and the kit blocks and `Standards:` line of `AGENTS.md` and
   `CLAUDE.md`, and the `Standards:` line must name a newer version than the base branch's. The
   changelog line and everything else `apply` wrote (`.gitignore`, settings, hooks,
   `scripts/check`, new read-before rows) go in the second.
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
