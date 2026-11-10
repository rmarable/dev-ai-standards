# W1 coverage: distill rows to files

Rows with destination core, an add-on, refs or a stack (109 rows). Each lands in exactly one file.
"no words" = covered by existing text of that section, as the distill row says.

| Row | File | Section |
|---|---|---|
| 1 | core.md | Core, rule 1 |
| 2 | core.md | Core, rule 2 |
| 3 | core.md | Core, rule 3 (Confirm rule) |
| 4 | core.md | Core, `AGENTS.md` bullet |
| 5 | core.md | Core, `AGENTS.md` bullet (read-before table) |
| 6 | core.md | Core, `AGENTS.md` bullet (no words; mechanism in templates) |
| 13 | core.md | Core, "One document owns each topic" |
| 20 | core.md | Core, targeted tests bullet |
| 24 | core.md | Core, secrets bullet |
| 33 | core.md | Core, trailer/semver bullet |
| 35 | core.md | Core, trailer/semver bullet ("tags only on approval") |
| 37 | core.md | Core, trailer/semver bullet (exact strings: addons/codex.md, see notes) |
| 38 | core.md | Core, CI bullet |
| 39 | core.md | Core, CI bullet ("a red run stops the next step") |
| 41 | core.md | Core, changelog bullet |
| 42 | core.md | Core, changelog bullet (no words) |
| 45 | core.md | Core, "Write terse, precise text" |
| 47 | core.md | Core, rule 2 (no words) |
| 77 | core.md | Core, Decisions bullet |
| 107 | core.md | Core, `AGENTS.md` bullet (no words; `rules_check`) |
| 109 | core.md | Enforcement, Ruleset |
| 117 | core.md | Core, `main` bullet |
| 131 | core.md | Scoped approval, first bullet |
| 145 | core.md | Model use |
| 153 | core.md | Model use |
| 21 | addons/high-stakes.md | Always loaded (gate 0 skipped) |
| 29 | addons/high-stakes.md | Real-service tests |
| 30 | addons/high-stakes.md | Always loaded (Phase R) |
| 31 | addons/high-stakes.md | Releases and tags |
| 34 | addons/high-stakes.md | Releases and tags |
| 43 | addons/high-stakes.md | Releases and tags |
| 62 | addons/high-stakes.md | Shared machine |
| 70 | addons/high-stakes.md | Reviews, Models |
| 71 | addons/high-stakes.md | Reviews, Models (out of credits) |
| 83 | addons/high-stakes.md | Reviews, Sizes |
| 84 | addons/high-stakes.md | Reviews, How a round runs |
| 85 | addons/high-stakes.md | Reviews, Diff review |
| 86 | addons/high-stakes.md | Gate |
| 87 | addons/high-stakes.md | Gate |
| 88 | addons/high-stakes.md | Gate (Docs only) + Local-gate status |
| 97 | addons/high-stakes.md | Model checks |
| 98 | addons/high-stakes.md | Model checks |
| 99 | addons/high-stakes.md | Model checks |
| 100 | addons/high-stakes.md | Model checks |
| 102 | addons/high-stakes.md | Releases and tags |
| 130 | addons/high-stakes.md | Reviews (subagents read-only) |
| 141 | addons/high-stakes.md | Reviews (never offer lighter) |
| 142 | addons/high-stakes.md | Writing and fixing rules |
| 144 | addons/high-stakes.md | Reviews, Fix checks (+ review-pending line from row 20's note) |
| 146 | addons/high-stakes.md | Reviews, Fix checks (lows-only) |
| 149 | addons/high-stakes.md | Writing and fixing rules |
| 150 | addons/high-stakes.md | Writing and fixing rules |
| 151 | addons/high-stakes.md | Writing and fixing rules (loosening) + Stop rule (holes) |
| 157 | addons/high-stakes.md | Writing and fixing rules, Stop rule |
| 158 | addons/high-stakes.md | Writing and fixing rules, Fix loop |
| 8 | addons/codex.md | Always loaded (reserved list) |
| 10 | addons/codex.md | Always loaded |
| 44 | addons/codex.md | Setup (CONTRIBUTING) |
| 53 | addons/codex.md | Codex's side, first bullet |
| 54 | addons/codex.md | Always loaded |
| 55 | addons/codex.md | Codex's side (own worktree) |
| 56 | addons/codex.md | Codex's side (`-NEW`) |
| 57 | addons/codex.md | Always loaded (`HANDOFF.md`) |
| 58 | addons/codex.md | Always loaded (no Claude state) |
| 60 | addons/codex.md | Codex's side (asks the operator) |
| 68 | addons/codex.md | Claude only (`CLAUDE.md`) |
| 69 | addons/codex.md | Claude's pick-up |
| 72 | addons/codex.md | Codex's side (doesn't review) |
| 110 | addons/codex.md | Setup |
| 111 | addons/codex.md | Setup |
| 112 | addons/codex.md | Setup (`Standards:` line) |
| 114 | addons/codex.md | Setup |
| 115 | addons/codex.md | Setup |
| 67 | addons/state-file.md | Path rule (Agreements) |
| 73 | addons/state-file.md | Intro + Path rule |
| 74 | addons/state-file.md | Path rule (placeholder) |
| 75 | addons/state-file.md | Claude only (when to update) + Path rule (Shape, Limits) |
| 76 | addons/state-file.md | Path rule (re-read, own lines) |
| 78 | addons/state-file.md | Path rule (Rewrite, don't append) |
| 79 | addons/state-file.md | Path rule (done items) |
| 80 | addons/state-file.md | Path rule (one short line) |
| 81 | addons/state-file.md | Path rule (delete stale) + Limits (14-day) |
| 82 | addons/state-file.md | Claude only (no confirmation, named in reply) |
| 36 | addons/planning.md | Milestones on main |
| 95 | addons/planning.md | Plan shape |
| 96 | addons/planning.md | Plan shape |
| 106 | addons/planning.md | Links between records |
| 147 | addons/planning.md | Saving planning sessions (briefs) |
| 61 | addons/multi-session.md | Always loaded |
| 63 | addons/multi-session.md | Rules |
| 64 | addons/multi-session.md | Rules |
| 65 | addons/multi-session.md | Rules |
| 66 | addons/multi-session.md | Claude only (`CLAUDE.md`) |
| 48 | refs/honesty.md | H2 |
| 105 | refs/outside-sources.md | S2, S6 |
| 17 | stacks/python.md | Toolchain |
| 18 | stacks/python.md | Toolchain |
| 89 | stacks/python.md | Tests |
| 118 | stacks/python.md | Toolchain (pyright) |
| 120 | stacks/python.md | Tests |
| 124 | stacks/python.md | CI |
| 126 | stacks/python.md | Dependencies and licences |
| 161-167 | stacks/iac.md | AWS Guidance (verbatim, one bullet each) |

Rows not placed: none.
