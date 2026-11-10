# Planning add-on

How plans are named, written, saved and linked. Applies to new documents only; existing documents
are never renamed or moved.

## Always loaded (`AGENTS.md` block `planning`)

- Read `docs/standards/addons/planning.md` before writing or changing a plan, milestone or task
  brief.

## Naming

| Kind | Path |
|---|---|
| Milestone | `planning-docs/milestones/M<n>-<slug>.md` |
| Other plan | `planning-docs/P<nnn>-<slug>.md` |
| Release plan | `planning-docs/releases/v<X.Y.Z>-<slug>.md` |
| Several files | a folder of that name: `README.md` (the plan), `step-<n>.md`, `review-<n>.md`, `codex-<topic>.md` |
| Finished | unchanged path; header says `done` |

Slugs are lowercase kebab-case, at most 5 words, with no status, date, draft or version words. IDs
are never reused. Codex writes `P-NEW`; it is renamed at merge in its own pure-rename commit.

## Plan shape

- First line: `ID · Status · Owner · Created · Updated · Milestone · Tier`.
- Tail sections: Decisions, Rejected, Open questions, Draft history.
- The header and tail own the plan's status; `ready` or `blocked` lives only there.
- A code reference names the commit it was checked against.

## Milestones on main

New milestones (the default for new ones only):
- The plan lives on `main`. Unbuilt spec text stays in the milestone doc until its step builds it.
- The build runs in short step branches, each merged through the gate. Unfinished behaviour stays
  unreachable.
- A long-lived branch only by recorded exception.
- When a milestone looks complete, tell the operator its tag is due and what is and isn't done.

## Saving planning sessions

- Plan-mode files are scratch; an approved plan is copied into the repo before anything is built.
- Drafts go on a `plan/<slug>` branch, merged each round with the operator's OK.
- A decision made in chat becomes an ADR or spec entry in the same session.
- Raw review output stays in `state-archive/<task>/`; the plan gets one line per round.
- Briefs go to a file once. Agents get the path and a lens and return a summary; peers get one line
  and a path. A brief names files and line ranges, caps the answer, uses one agent per lens and says
  what is already verified.

## Resume card

Atop `state-archive/<task>/log.md`, at most 15 lines: goal, status, next action, read first,
settled decisions, running processes. A fresh session reads it before anything else in the task.

## Links between records

Each record has one owner; the others point to it.
- Plan doc: owns status, steps, decisions in progress. Links its ADRs and spec sections by ID.
- ADR or dated spec line: owns a decision. The plan's Decisions line and the commit name it.
- `CHANGELOG.md`: one line per user-visible change, ending with the plan, ADR or decision ID.
- State file: one pointer per task (plan path, log path, next action), never the content.
- `state-archive/<task>/log.md`: resume card and step detail; links back to the plan.
- When rules move between files, a script checks that every old line maps to new text or an
  approved drop.
