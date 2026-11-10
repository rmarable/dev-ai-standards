# dev-ai-standards

Shared working rules and tooling for repositories where Claude Code, and optionally Codex, write
the code. Agents drift from their rules, and rules drift apart between projects. The kit copies one
rule set into each project, hashes every copied file, and fails CI when a project's copy changes.

## Quick start

You need macOS, git, `python3` 3.9 or later, a logged-in GitHub CLI (`gh`) and Claude Code 2.1.251
or later.

```sh
git clone https://github.com/rmarable/dev-ai-standards.git ~/src/dev-ai-standards
ln -s ~/src/dev-ai-standards/bin/new-claude-project ~/src/dev-ai-standards/bin/dev-ai-standards ~/.local/bin/
export NEW_CLAUDE_PROJECT_OWNER=<your GitHub login>
new-claude-project inventory-api --stack python
```

1. It builds `~/src/inventory-api` and asks for any choice you left out.
2. It lists the files and GitHub actions, then asks one y/N.
3. On yes it commits, creates a private GitHub repo, pushes, and adds branch protection where your plan allows.
4. It opens Claude Code to plan the first milestone with you.
5. On failure it stops, lists what exists and deletes nothing.

## What a project gets

| Item | Purpose |
|---|---|
| `AGENTS.md`, `CLAUDE.md` | The rules; `CLAUDE.md` imports `AGENTS.md`, so both agents read one source. |
| `docs/standards/` | Kit rule files and checks, plus a manifest of their hashes. |
| Hooks | Git `commit-msg` and `pre-commit` checks; Claude Code hooks that warn when the agent's notes file grows too large. |
| CI workflows | `rules-check` on every push and pull request; Python tests for the python stack. |
| `scripts/check` | Runs exactly what CI runs. Python: ready as written ("no tests yet" until tests exist). Other stacks: fails until you add steps. |
| `planning-docs/` | A plan index and the first milestone's plan. |

## The core rules, in brief

- Don't lie or make up facts; a verified fact cites its source and date.
- Confirm with you before writing files, committing or pushing, unless you granted a scoped approval.
- `main` changes only through a pull request with a merge commit; your approval or merge is the OK.
- After every push, watch CI to the end; a failed run stops the next step.
- One co-author trailer per commit, naming the agent that did the work.
- Secrets live only in a secret store, never in the repo, environment or files.

## Options

- **Core** (default): the rules above only.
- **`--high-stakes`**: sized reviews before building, and a full test gate with nothing skipped on every merge.
- **`--codex`**: rules for running Codex beside Claude Code.
- **`--stack python`**: uv, Ruff, pyright and pytest. Adds `pyproject.toml`; new projects also get `uv.lock`, so CI passes from the first push.
- **`--stack iac`**: AWS guidance for infrastructure code.
- **`--stack other`** (default): no toolchain rules; you list the project's commands.

## Existing projects

On a branch, run `dev-ai-standards apply [options] <dir>`. It adds kit files and blocks, never
overwrites project-owned text, and installs git hooks only if the repo has none. Commit the
reviewed diff.

## Updating

Pull the kit and read its changelog. In the project, on a branch, run `dev-ai-standards drift`,
resolve hand edits to kit text, and re-run `apply` with the same options. The upgrade pull request
may change only kit text; the rest of `apply`'s output goes in a second one.

## Codex (optional)

Codex edits files only in its own worktree on a `codex/<topic>` branch and writes `HANDOFF.md`.
Claude Code reads the handoff and diff, runs the checks, commits and opens the pull request; Codex
makes no git writes. This loop was piloted on 2026-11-10. A script that runs `codex exec` must
close its stdin (`< /dev/null`).

## Limits

- Hooks are reminders; `git commit --no-verify` skips them. CI is the real check.
- GitHub Free gives private repos no branch protection; the launcher skips it, or warns and finishes if GitHub refuses. Public repos get it.
- The secret scan is a tripwire for common credential formats, not a guarantee.
- The iac stack is unproven: no project has used it.

## More

- [docs/reference.md](docs/reference.md): flags, variables, files written.
- [checks/README.md](checks/README.md): what each check enforces.
- [CHANGELOG.md](CHANGELOG.md): changes by version.
- [Design plan](planning-docs/P001-dev-ai-standards.md): decisions and rejected options.
