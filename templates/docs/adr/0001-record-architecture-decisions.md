# ADR 0001: Record architecture decisions

- Status: accepted
- Date: {{date}}

## Context

Decisions made while building get lost in chat, commit messages and agent sessions. Agents need
them in the repository, where both Claude Code and Codex can read them.

## Decision

- Each significant decision is an ADR in `docs/adr/NNNN-<slug>.md`: Status, Date, Context,
  Decision, Consequences, and Rejected where alternatives were weighed. Numbers are never reused.
  On a branch everyone writes `ADR-NEW`; the real number is assigned when merging to `main`.
- A small decision that doesn't justify an ADR (a default value, a name) is a dated "operator
  decision" line in the spec section it changes. Either way, the commit message names it.
- An ADR is not edited after it is accepted, except its Status line. Status is proposed,
  accepted, superseded by a later ADR, or withdrawn. A later ADR that replaces this one says
  "Supersedes" and this one's number, and this one's Status names the later ADR (planning add-on,
  "Retiring a decision").
- The project follows dev-ai-standards v{{version}} ({{choices}}), as its `AGENTS.md` `Standards:`
  line records. Changes to kit rules go through `AGENTS.md` `## Overrides` or a PR on the kit.

## Consequences

- Reasons survive the session that made them; reviewers and new agents read them first.
- A decision found only in chat or a state file is not yet made: write it here or in the spec.
