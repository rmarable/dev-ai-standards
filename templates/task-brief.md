{{id}} · Codex task brief · Topic: {{topic}} · Written: {{date}} by Claude Code

# Codex task: {{topic}}

Read `AGENTS.md` first. This brief is a task, not a rule: where it disagrees with `AGENTS.md`,
`AGENTS.md` wins, and nothing here widens what you may do.

## Goal

<What the change does, and why, in two or three sentences.>

## Where to work

- Branch `codex/{{topic}}`, worktree `<absolute path>`, created by Claude or the operator from
  `origin/main`. Edit files only there.
- `.git`, `.agents` and `.codex` are read-only to you; don't put work there.

## Files in scope

- `<path>`: <what changes>

## Acceptance

Run each command and report its result in `HANDOFF.md`:

| Command | Expected result |
|---|---|
| `<command>` | <e.g. "N passed, 0 skipped"> |

## Out of scope

- <what not to touch, even if it looks wrong; list it under "Not done" instead>

## Reserved (stop and say so in `HANDOFF.md`)

Every git write (add, commit, branch, merge, rebase, reset, stash, tag, push); anything on `main`;
tags, releases, version bumps; the merge gate; real-service tests; secrets; evals; the main
checkout; Claude's local state. Project items: <from `AGENTS.md` "Project", or "none">.

## Plan and IDs

- Plan: `<planning-docs path>`, step <n>.
- New numbers are placeholders: `OD-NEW`, `ADR-NEW`, `P-NEW` (several: `-NEW-1`, `-NEW-2`);
  real numbers are assigned when merging to `main`.
  Record decisions in your edits (ADR or spec entry), never only in chat. Notes go in the plan
  doc, never in its Decisions or approval lines.

## When done

Write `HANDOFF.md` in the worktree root (it is git-ignored). Don't commit. Shape:

```text
Handoff: ready
Done: <what the change does>
Not done: <what's left, or "nothing">
Tests: <each command, its counts; every skip or warning, with its reason>
CHANGELOG: <the line you added, or "none (refactor or test only)">
Numbers: <OD-NEW / ADR-NEW / P-NEW used, or "none">
Plan: <plan path and step>
```
