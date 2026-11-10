# ADR 0001: dev-ai-standards, a shared kit of agent rules

- Status: accepted
- Date: 2026-11-10
- Plan: `planning-docs/P001-dev-ai-standards.md` (owns the full text, the reasons and every
  operator decision; this record lists the main ones and points there).

## Context

One working project had grown practices that work (one rule file for Claude Code and Codex,
recorded decisions, trailer and changelog rules, CI watching, review before building, a merge gate
with 0 skipped), but they lived in one repository and had drifted from the skill that copied them.
The team's new projects (Python, IaC, mixed) need the same rules without the weight.

## Decision

1. **A kit repository**, `rmarable/dev-ai-standards`, private. A one-page core (`core.md`, at most
   600 words by `wc -w`: Core, Enforcement, Scoped approval, Model use) goes inline into every
   project's `AGENTS.md`; heavier rules are add-ons (high-stakes, codex, state-file, planning,
   multi-session) and stacks (python, iac, other). P001 "Part A".
2. **Copy, don't link.** `apply` copies kit text into `docs/standards/` and marked `AGENTS.md`
   blocks and writes a hash manifest; kit text is never edited in a project. A project changes a
   kit rule through `## Overrides` or `promote`. `drift` and `rules_check` compare against `main`'s
   manifest. P001 "Kit-owned and project-owned text".
3. **Enforcement in three layers:** GitHub refuses (a ruleset on `main` and `v*` tags, no bypass
   list, turned on by the operator), CI reports (an unfiltered rules-check with checks from the
   base branch), the rest are reminders (`permissions.ask`, hooks). Agents never change remote
   settings. On GitHub Free a private repo gets no ruleset; the launcher skips it and says so (A4
   tries it once). P001 "Enforcement".
4. **PRs by default** for new projects, merged with a merge commit; the operator's approval or
   merge is the OK. `--no-pr` keeps local `--no-ff` merges. P001 Decisions, draft 3 (4).
5. **Scoped approval:** granted only by the operator's own message, bound to one step's branch;
   never covers `main`, tags, releases, deletions, settings, outside services, weakening a check,
   heavy runs or dependency changes. P001 "Scoped approval".
6. **Model use:** the main session runs the strongest model, routine subagents the routine model,
   which never reviews; reviews default to Opus, with Fable only for big-picture rounds at sizes 1
   to 8. Review sizes 1, 2, 4, 8, 12, 16. P001 "Model use", "High-stakes add-on".
7. **Codex edits, Claude commits:** Codex only edits files in a `codex/*` worktree and writes a
   git-ignored `HANDOFF.md`; Claude does every git write, commits hooks-off and pushes with main's
   hooks. Unproven until A4. P001 "Codex add-on", final decision 2.
8. **Three checks for v1.0:** `trailer_check` (exactly one allowed co-author trailer:
   `Co-Authored-By: Claude <noreply@anthropic.com>` or `Co-Authored-By: Codex
   <noreply@openai.com>`, never naming a model), `rules_check`, `state_check` (warn-only). Other
   checks are deferred (`CHANGELOG.md`). P001 "The three v1.0 checks".
9. **One-command launch:** `new-claude-project`; Claude may run `--dry-run` and `--local`; remote
   steps need an interactive human y/N. P001 "One-command launch", final decision 3.
10. **Versioning:** `v0.x` until the first real adopter's adoption merges; `v1.0` is tagged on the
    kit commit it adopted. P001 step A5.

## Consequences

- Every project carries the same core and can be checked for drift by script.
- Protection on private repositories rests on CI and reminders until the account can hold
  rulesets.
- The Codex loop, the `permissions.ask` patterns, the rules-check workflow's pinned actions and the
  facts marked unknown in `planning-docs/P001-notes/a0-facts.md` are unproven until A4.
- Personal preferences stay in `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`, outside the kit.

## Rejected

See P001 "Rejected" (graph memory, changelog fragments, bypass lists, Codex committing with pinned
hooks, local merges as the default, among others).
