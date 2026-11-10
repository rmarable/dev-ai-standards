# ADR 0001: Record architecture decisions

- Status: accepted
- Date: {{date}}

## Context

Decisions made while building get lost in chat, commit messages and agent sessions. Agents need
them in the repository, where both Claude Code and Codex can read them.

## Decision

- Each significant decision is an ADR in `docs/adr/NNNN-<slug>.md`: Status, Date, Context,
  Decision, Consequences, and Rejected where alternatives were weighed. Numbers are never reused;
  Codex writes `ADR-NEW`, and Claude assigns the number at merge.
- A small decision that doesn't justify an ADR (a default value, a name) is a dated "operator
  decision" line in the spec section it changes. Either way, the commit message names it.
- An ADR is not edited after it is accepted, except its Status line; a later ADR supersedes it and
  says so.
- The project follows dev-ai-standards v{{version}} ({{choices}}), as its `AGENTS.md` `Standards:`
  line records. Changes to kit rules go through `AGENTS.md` `## Overrides` or a PR on the kit.

## Consequences

- Reasons survive the session that made them; reviewers and new agents read them first.
- A decision found only in chat or a state file is not yet made: write it here or in the spec.
