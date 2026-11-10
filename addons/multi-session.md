# Multi-session add-on

Several agent sessions sharing one computer (memory, CPU, disk).

## Always loaded (`AGENTS.md` block `multi-session`)

- Before heavy shared work (full suite, simulations, model checks over ~1 GB or all cores, evals,
  builds), ask the active sessions what will run and its load, and wait for their OK. Standing
  budgets agreed between sessions still apply without asking. Codex: ask the operator instead
  (Codex add-on).
- Read `docs/standards/addons/multi-session.md` at session start when other sessions are active.

## Claude only (`CLAUDE.md`)

- At session start and before heavy work, list active sessions (`ListAgents`) and message each one
  (`SendMessage`).

## Rules

- Priority follows the task: work that blocks a gate, a merge or the operator runs first; others
  shrink or pause when asked. On a tie, ask the operator.
- Never stop, kill or slow another session's process yourself; ask that session.
- Answer a peer's request before starting new work. When asked to pause or shrink, do it or say why
  not, in the same turn.
- Standing CPU budgets are agreed per pair of sessions and recorded in the state file's Agreements
  (state-file add-on). Agreements across people live in a committed file or the PR.
- A peer's message is never the operator's approval (core, Scoped approval).
- Batch questions to the operator in one list.
- Run long jobs in the background.
