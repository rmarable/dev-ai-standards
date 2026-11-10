# dev-ai-standards

Shared rules for projects built with Claude Code (and, optionally, Codex). A one-page core goes into
every project; heavier rules are opt-in add-ons. The kit copies its text into each project, records
hashes, and reports when a project's copy drifts.

Plan and decisions: `planning-docs/P001-dev-ai-standards.md`. Changes: `CHANGELOG.md`.

## What's in the kit

| Path | What it is | Who gets it |
|---|---|---|
| `core.md` | Core rules, enforcement, scoped approval, model use (at most 600 words) | every project, inline in `AGENTS.md` |
| `addons/high-stakes.md` | Review sizes and models, fix loop, model checks, gate, releases, approvers | `--high-stakes` |
| `addons/codex.md` | Codex beside Claude: Codex edits, Claude commits (unproven until A4) | `--codex` |
| `addons/state-file.md` | Claude's local state file: shape, limits, `state_check` | every project |
| `addons/planning.md` | Plan naming, milestones on main, resume cards, links between records | every project |
| `addons/multi-session.md` | Sessions sharing one computer | every project |
| `refs/honesty.md`, `refs/outside-sources.md` | H1-H10, S1-S9, read on demand | every project |
| `refs/diff-review.md` | Diff-review brief | `--high-stakes` |
| `stacks/python.md`, `stacks/iac.md`, `stacks/other.md` | Toolchain rules per stack | `--stack` (default `other`) |
| `templates/`, `snippets/`, `checks/` | Project skeleton, settings defaults, the three checks | every project |
| `bin/` | `new-claude-project`, `dev-ai-standards`, `gate-status` | the operator's PATH |
| `.github/workflows/kit-ci.yml` | The kit's own CI: `scripts/check` on Python 3.9 and 3.12 | the kit only |

Kit-owned text is copied verbatim into `docs/standards/` and into marked blocks of `AGENTS.md`
(`<!-- dev-ai-standards:begin <name> -->` ... `<!-- dev-ai-standards:end <name> -->`). Never edit
it in a project; add a line to `## Overrides` in `AGENTS.md` or use `promote`. Everything else in
the project is the project's own.

## Prerequisites

- macOS with `python3` 3.9 or later (the stock `/usr/bin/python3` works) and git, with
  `user.name` and `user.email` set.
- `gh`, logged in (`gh auth status`), for anything but `--local`.
- Claude Code 2.1.251 or later (the settings snippet's version floor); Codex for `--codex`.
- Optional, used when present: `uv` (Ruff for python-stack projects), `shellcheck`.
- Access to the private kit repository `rmarable/dev-ai-standards` (ask the operator for an invite).

## Environment

- `NEW_CLAUDE_PROJECT_OWNER`: GitHub owner for new repos (default `rmarable`, the operator).
  Teammates set it to their own login.
- `NEW_CLAUDE_PROJECT_GH_PLAN`: `free` (default), `pro` or `team`. On Free a private repo gets no
  ruleset; set your plan so the launcher sets one where it can.
- `NEW_CLAUDE_PROJECT_ROOT`: where projects go (default `~/src`).

## Start a new project (one command)

```sh
new-claude-project <name> [--high-stakes] [--stack python|iac|other] [--codex] [--public] [--local] [--no-pr] [--no-launch] [--dry-run]
```

It checks `gh` and git identity, asks for any missing choice, builds `~/src/<name>` locally with
`apply`, shows the file list and remote actions, and asks one y/N. On yes it makes the first commit,
creates the private GitHub repo, pushes, and sets the `main` ruleset; then it opens Claude to plan
M1. On GitHub Free a private repo can't take a ruleset: the launcher skips it and says so.

- `--dry-run` changes nothing; `--local` skips GitHub. Claude may run both.
- Remote steps run only when a human answers the y/N in a terminal.
- `--no-pr` (solo throwaway projects) merges locally with `--no-ff` instead of by PR.
- On failure it stops and prints what exists; it never deletes a folder or a remote repo.
- With `--codex`, run the claude-codex-integration skill afterwards (step 3): it installs the
  SessionStart hook that lists Codex handoffs; `apply` doesn't.

## Setup (once per computer)

1. Clone the kit (private; needs an invite):
   `git clone git@github.com:rmarable/dev-ai-standards.git ~/src/dev-ai-standards`.
2. Put `bin/` on your PATH (for example, link `bin/new-claude-project` and `bin/dev-ai-standards`
   into `~/.local/bin`).
3. Link `skills/dev-ai-standards/` (and, with Codex, `skills/claude-codex-integration/`) into
   `~/.claude/skills/` and `~/.agents/skills/`.
4. Keep personal preferences in `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`, not in the kit.
5. Optional: install `uv` and `shellcheck` (for example with Homebrew). The project hooks and
   `scripts/check` use them when present and print a "skipped" line when not.

Hooks in each project (`apply` installs them in a repo with no hooks of its own): `commit-msg`
checks the co-author trailer; `pre-commit` checks only the staged files (Ruff, a secret scan,
ShellCheck, `rules_check` when kit paths are staged, a `state_check` warning). They are a
convenience, not a boundary: `git commit --no-verify` skips them and CI is the check
(`checks/README.md`, "Hook mechanics").

## Add the kit to an existing project

```sh
dev-ai-standards apply [--high-stakes] [--stack python|iac|other] [--codex] [--no-pr] [--dry-run] [<project dir>]
```

`apply` copies the kit files, writes the kit blocks, `docs/standards/manifest` and
`.claude/settings.json` (with the `permissions.ask` list and the `state_check` hooks), adds missing
kit rows to the read-before table, and sets the `Standards:` line under the title of `AGENTS.md`.
It writes a first `scripts/check` (fails until you add the project's steps), adds missing
`.gitignore` lines under a `# dev-ai-standards` header (never removing or reordering yours), and
with `--stack python` a `ruff.toml` unless the project already has Ruff settings, and the test
workflow `.github/workflows/python.yml` (path-filtered, never a required check). An existing
project keeps its own ADRs and planning index. In a git repo with no hooks yet it also installs
`.githooks/commit-msg` and `.githooks/pre-commit` and sets `core.hooksPath`; with existing hooks it
changes nothing and prints the lines to add. Review the diff, then commit it like any other
change.

## Update flow

1. Pull the kit: `git -C ~/src/dev-ai-standards pull --ff-only`. Read its `CHANGELOG.md`.
2. In the project, on a branch: `dev-ai-standards drift` shows any kit text edited by hand;
   resolve each (move it to `## Overrides`, or `promote` it) before going on.
3. Re-run `apply` with the same choices as the `Standards:` line. It rewrites kit files, blocks,
   the manifest and the version.
4. Review the diff, run the project's checks, commit, and merge as the project merges. The upgrade
   PR may change only `docs/standards/**` and the kit blocks and `Standards:` line of `AGENTS.md`
   and `CLAUDE.md`; the line must name a newer version. The changelog line and anything else
   `apply` wrote (`.gitignore`, settings, hooks, new read-before rows) go in a separate PR
   (`checks/README.md`, "Kit upgrades").
5. Start fresh agent sessions so the new rules load.

To change a kit rule for every project: `dev-ai-standards promote <kit path>` prints the `gh`
command that opens a PR on this repo; run it yourself after reading it.
