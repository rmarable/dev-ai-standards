# dev-ai-standards

Shared working rules and tooling for repositories where Claude Code, and optionally Codex, write
the code. Agents drift from their rules, and rules drift apart between projects. The kit copies one
rule set into each project, records a fingerprint of every copied file, and makes GitHub's
automatic checks fail when a copy changes.

## Quick start

You need macOS, the Xcode Command Line Tools, git and uv (uv fetches Python 3.12 itself), plus a
logged-in GitHub CLI (`gh`) and Claude Code 2.1.251 or later. `bin/bootstrap` checks the first
three and prints install commands.

```sh
git clone https://github.com/rmarable/dev-ai-standards.git ~/src/dev-ai-standards
~/src/dev-ai-standards/bin/bootstrap
ln -s ~/src/dev-ai-standards/bin/new-claude-project ~/src/dev-ai-standards/bin/dev-ai-standards ~/.local/bin/
export NEW_CLAUDE_PROJECT_OWNER=<your GitHub login>
new-claude-project inventory-api --stack python
```

It builds `~/src/inventory-api`, asks for missing choices, lists the files and GitHub
actions, and asks one y/N. On yes it commits, creates a private GitHub repo, pushes, adds branch
protection where your plan allows, and opens Claude Code to plan the first milestone. On failure
it stops and deletes nothing.

## What a project gets

| Item | Purpose |
|---|---|
| `AGENTS.md`, `CLAUDE.md` | The rules; `CLAUDE.md` imports `AGENTS.md`, so both agents read one source. |
| `docs/standards/` | Kit rule files and checks, plus a list of their fingerprints. |
| Hooks | Git `commit-msg` and `pre-commit` checks; a Claude Code warning when its notes file grows too large. |
| GitHub Actions workflows | Automatic checks GitHub runs: `rules-check` on every push and pull request; Python tests for the python stack. |
| `scripts/setup` | Run once after cloning: checks your tools and turns on the git hooks. |
| `.github/CODEOWNERS`, `## People` in `AGENTS.md` | Owner and approvers, by GitHub login. |
| `scripts/check` | Runs the same checks on your machine that GitHub runs. Ready for Python; other stacks fail until you add steps. |
| `planning-docs/` | A plan index and the first milestone's plan. |

## The core rules, in brief

- Agents don't lie or make up facts. A verified fact cites its source and date.
- Agents confirm with you before they write files, commit or push, unless an approver granted a scoped approval (a recorded permission for one step).
- `main` changes only through a pull request with a merge commit. Your approval or merge is the OK.
- After every push, the agent watches GitHub's automatic checks to the end. A failed run stops the next step.
- Each commit has exactly one co-author trailer, naming the agent that did the work: `Claude <noreply@anthropic.com>` or `Codex <noreply@openai.com>`. It never names a model.
- Secrets live only in a secret store, never in the repo, the environment or files.

## Options

- **Core** is the default. The project gets only the rules above.
- **`--high-stakes`** adds sized reviews before building, and a full test gate with nothing skipped on every merge.
- **`--codex`** lets Codex work in its own `codex/<topic>` branch and worktree, without git writes. Claude Code reviews its work, commits and opens the pull request.
- **`--stack python`** sets up uv, Ruff, pyright and pytest. It writes `pyproject.toml`, and `uv.lock` in new projects, so GitHub's checks pass from the first push.
- **`--stack iac`** adds AWS guidance for infrastructure code.
- **`--stack other`** is the default stack. It adds no toolchain rules, and you list the project's commands.

## Joining a project

1. Clone the repository.
2. Run `scripts/setup`. It checks your tools, then turns on the git hooks unless your clone uses
   other hooks.
3. Put personal preferences in `~/.claude/CLAUDE.md` (Codex: `~/.codex/AGENTS.md`), not in the
   repository.

Agents take approvals only from approvers under `## People` in `AGENTS.md` on `main`.

## Existing projects

On a branch, run `dev-ai-standards apply [options] <dir>`. It adds kit files and blocks, never
overwrites project-owned text, and installs git hooks only if the repo has none. Commit the
reviewed diff.

## Updating

Pull the kit and read its changelog. On a project branch, run `dev-ai-standards drift`,
resolve hand edits to kit text, and re-run `apply` with the same options. The upgrade pull request
holds only kit text, plus hooks and `scripts/check` when a release changes how they start; the
rest goes in a second one.

## Limits

- Hooks are reminders, and `git commit --no-verify` skips them. GitHub's automatic checks are the real check.
- Required reviews and branch protection on private repos need a paid GitHub plan (Team or Pro, unverified). On GitHub Free, you rely on GitHub's automatic checks and the reminders.
- Agents can't verify who is typing. `## People` is a policy, not a login.
- The secret scan is a tripwire for common credential formats, not a guarantee.
- The iac stack is unproven: no project has used it.

## More

- [docs/reference.md](docs/reference.md) lists the flags, the environment variables and the files the kit writes.
- [checks/README.md](checks/README.md) describes what each check enforces.
- [CHANGELOG.md](CHANGELOG.md) lists the changes in each version.
- The [design plan](planning-docs/P001-dev-ai-standards.md) records the decisions and the options that were rejected.
