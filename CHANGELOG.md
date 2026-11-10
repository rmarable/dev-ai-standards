# Changelog

One line per user-visible change, newest first, at most 200 characters, ending with its ID.
Sections: Added, Changed, Fixed, Removed, Deprecated, Security. Semantic versioning; at tagging, the
heading becomes the tag and its date.

## v0.1.0 (not yet tagged)

### Added

- `skills/dev-ai-standards` (runs `bin/dev-ai-standards`) and `skills/claude-codex-integration` v2, "Codex edits, Claude commits" (P001).
- Snippets: Claude Code settings (subagent model, trailer, `permissions.ask`) and Codex config defaults; neither is a security control (P001).
- Templates: `AGENTS.md`, `CLAUDE.md`, gitignore, gitattributes, changelog, ADR 0001, planning index, milestone, Codex task brief, state file (P001).
- `templates/ci/rules-check.yml`: unfiltered, read-only, checks and manifest from the base branch; action SHAs to verify at A4 (P001).
- Checks: `trailer_check`, `rules_check`, `state_check` (warn-only) (P001).
- `bin/dev-ai-standards` (apply, drift, promote), `bin/gate-status` and the `bin/new-claude-project` launcher (P001).
- Stacks: python; iac (unproven); other (P001).
- Refs read on demand: honesty H1-H10, outside sources S1-S9, diff-review brief (P001).
- Add-ons: high-stakes, codex (unproven until A4), state-file, planning, multi-session (P001).
- `core.md`: core rules, enforcement, scoped approval and model use, at most 600 words (ADR 0001).

## Deferred past v1.0

Not built in v1.0 (P001 "The three v1.0 checks"): link-graph and dead-link checks; planning README
sync; changelog format check; fragment hook; secret-scan hook (projects may add one); Handoff format
check; scripted canary diff (manual at A4); Codex memory listing; branch-behind warning; size
report; version-floor check.
