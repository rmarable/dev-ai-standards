# Changelog

One line per user-visible change, newest first, at most 200 characters, ending with its ID.
Sections: Added, Changed, Fixed, Removed, Deprecated, Security. Semantic versioning; at tagging, the
heading becomes the tag and its date.

## v0.1.0 (not yet tagged)

### Security

- rules-check: a forced push to the default branch fails; any other branch compares with its merge-base with the default branch (F1-1).
- gate-status: `--no-fetch`, `--list` and `--script-path` removed; it always fetches and checks the PR's base (F1-2).
- secret_scan parses diffs by hunk and prints file and line only, never line content (F1-4).
- `.claude/rules/state-file.md` is kit text again, under one fixed manifest key (F1-9).
- rules-check on a push compares with the commit before the push, never the pushed commit; force pushes and pushes with no merge-base fail (K1-1).
- A kit upgrade may touch only `docs/standards/**` and kit blocks; manifest keys outside that set fail and stop `apply` (K1-2, K1-5).
- trailer_check fails a force push to the base branch; gate-status treats nested agent files as enforcement and pins its base, list and context (K1-3, K1-4, K1-6).

### Added

- `refs/user-docs.md` and `.claude/rules/user-docs.md` (loaded for README.md and docs/**), plus a read-before row: rules for user-facing docs (doc rules).
- `apply --stack python` writes `pyproject.toml` when absent; the launcher runs `uv lock` before the first commit, so python.yml passes (A4 pilot).
- Python-stack `scripts/check` passes on a fresh project: pytest runs once tests exist, else "no tests yet"; other and iac still fail until edited (A4 pilot).
- new-claude-project: GitHub Free's ruleset 403 on a private repo is a warning; the launcher finishes; the failure summary shows the repo's state at that moment (A4 pilot).
- README rewritten for new users; detail moved to docs/reference.md (doc rules).

- `apply --stack python` writes `.github/workflows/python.yml` (test CI, path-filtered, never required); kit CI in `.github/workflows/kit-ci.yml` (G5).
- shell_lint checks zsh files with `zsh -n` (syntax only) and takes files from git; the pre-commit hook finds Ruff without `uv run` (F1-5, F1-6, F1-13).
- State template renamed `templates/CLAUDE-STATE.template.md`; kit gitignore lines unanchored again (F1-3).
- `.githooks/pre-commit` (staged files only: Ruff, secret scan, ShellCheck, rules_check on kit paths, state_check warning) and `checks/secret_scan.py` (G3).
- ShellCheck in `scripts/check`, the pre-commit hook and CI; Codex handoff hook moved to `templates/hooks/codex-handoffs.sh` (G4).
- `templates/ruff.toml` for the python stack, and Ruff on the kit's own code (G2).
- A first project `scripts/check`, the state_check hooks in `.claude/settings.json`, and kit read-before rows on existing projects (K2-1, K2-2, K2-3).
- Base `.gitignore` with secrets and per-stack lists, merged append-only (G1).

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
