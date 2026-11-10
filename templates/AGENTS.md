# AGENTS.md

Standards: dev-ai-standards v{{version}} ({{choices}})

Rules for the coding agents working in this repository. Claude Code reads them through `CLAUDE.md`. Text between `dev-ai-standards` markers is kit-owned: never edit it here; change
it through `## Overrides` or `promote`.

<!-- if codex -->
<!-- dev-ai-standards:begin codex -->
<!-- dev-ai-standards:end codex -->

<!-- endif -->
<!-- dev-ai-standards:begin core -->
<!-- dev-ai-standards:end core -->

## Read before you do these

Rules in these files bind as if they were here. Each add-on block below names its own file.

| Before you… | Read |
|---|---|
| report a result, or say "done", "fixed" or "passes" | `docs/standards/refs/honesty.md` (H1-H10) |
| use an outside source (web page, vendor doc, package, API) | `docs/standards/refs/outside-sources.md` (S1-S9) |
| run the merge check (before staging Codex work or any merge ask) | `docs/standards/checks/README.md` (enforcement paths) |
<!-- if high-stakes -->
| run or brief a diff review | `docs/standards/refs/diff-review.md` |
<!-- endif -->
| <project task> | <project file> |

<!-- if high-stakes -->
<!-- dev-ai-standards:begin high-stakes -->
<!-- dev-ai-standards:end high-stakes -->

<!-- endif -->
<!-- dev-ai-standards:begin state-file -->
<!-- dev-ai-standards:end state-file -->

<!-- dev-ai-standards:begin planning -->
<!-- dev-ai-standards:end planning -->

<!-- dev-ai-standards:begin multi-session -->
<!-- dev-ai-standards:end multi-session -->

<!-- if python -->
<!-- dev-ai-standards:begin python -->
<!-- dev-ai-standards:end python -->

<!-- endif -->
<!-- if iac -->
<!-- dev-ai-standards:begin iac -->
<!-- dev-ai-standards:end iac -->

<!-- endif -->
<!-- if other -->
<!-- dev-ai-standards:begin other -->
<!-- dev-ai-standards:end other -->

<!-- endif -->
## Project

{{name}}: <what it is and who uses it, in two or three sentences>.

- Design owner: <the spec or doc that owns design, threat model and limits>.
- Commands: `scripts/check` runs what CI runs; `scripts/check --full` adds the full suite.
  <other commands a newcomer needs>
<!-- if high-stakes -->
- Risk area (Phase R trigger): <what a plan must change to need Phase R>.
- Gate: <what the full gate runs, and on which platform>.
- Approvers: <who approves main merges, tags and rule changes>.
<!-- endif -->
<!-- if codex -->
- Reserved for Claude, beyond the kit's list: <project items, e.g. deploys, live credentials, or
  "none">.
<!-- endif -->

## Overrides

<!-- One line per change to a kit block: "- <block name>: <what changes and why>". The override
wins; rules_check lists it. Leave empty when there are none. -->
