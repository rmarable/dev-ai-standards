# Planning add-on

How plans are named, written, saved and linked. Applies to new documents only; existing documents
are never renamed or moved.

## Always loaded (`AGENTS.md` block `planning`)

- Read `docs/standards/addons/planning.md` before writing or changing a plan, milestone or task
  brief.
- On a branch, new IDs are placeholders (`ADR-NEW`, `OD-NEW`, `P-NEW`); the real number is
  assigned before merging into the default branch.

## Naming

| Kind | Path |
|---|---|
| Milestone | `planning-docs/milestones/M<n>-<slug>.md` |
| Other plan | `planning-docs/P<nnn>-<slug>.md` |
| Release plan | `planning-docs/releases/v<X.Y.Z>-<slug>.md` |
| Several files | a folder of that name: `README.md` (the plan), `step-<n>.md`, `review-<n>.md`, `codex-<topic>.md` |
| Finished | unchanged path; header says `done` |

Slugs are lowercase kebab-case, at most 5 words, with no status, date, draft or version words. IDs
are never reused.

## IDs

Every record has an ID, and every new file under `planning-docs/` carries one:

| Record | ID | Where the ID is |
|---|---|---|
| Plan | `P<nnn>` (`P-NEW` on a branch) | file name `P<nnn>-<slug>.md`, and the start of its first line |
| Milestone | `M<n>` | file name `milestones/M<n>-<slug>.md`, and the start of its first line |
| Release plan | `v<X.Y.Z>` | file name `releases/v<X.Y.Z>-<slug>.md`, and the start of its first line |
| Plan folder | the plan's ID | folder name `<ID>-<slug>/`; its `README.md` starts with the ID |
| File in a plan folder | its plan's ID | the folder it sits in (`P012-cache/step-2.md` is P012's step 2) |
| ADR | `ADR-<nnnn>` (`ADR-NEW` on a branch) | file name `docs/adr/<nnnn>-<slug>.md`, and its title `# ADR <nnnn>: ...` |
| Decision | `OD-<n>` (`OD-NEW`, `OD-NEW-1` on a branch) | the start of its definition line, `- OD-<n>: ...` |
| Codex task brief | the plan's ID | the start of its first line |

`planning-docs/README.md`, the index, needs no ID. Decision and ADR numbers are each counted across
the whole repository, so an ID names one record in any plan or milestone. A decision is defined
once; when its text moves (for example from a milestone into the spec), the definition moves and
is not copied. `rules_check` fails a new file under `planning-docs/` without an ID, and an ID
defined twice. Files that already exist are never checked.

## Retiring a decision

A decision or ADR is never deleted or moved when it stops applying. It stays where it is, marked:

- **Superseded.** A new record replaces it. The old record gets `(superseded by <new ID>, <date>)`
  at the end of its definition line, and the new one says `Supersedes <old ID>`. For an ADR, the
  old one's Status becomes `superseded by ADR-<nnnn>` and the new one says `Supersedes
  ADR-<nnnn>`. Both links are required.
- **Withdrawn.** It is dropped with no replacement. The record gets `(withdrawn, <date>: <reason>)`;
  an ADR's Status becomes `withdrawn`.

ADR Status is one of `proposed`, `accepted`, `superseded by ADR-<nnnn>` or `withdrawn`. Marking a
record is the only edit allowed to an accepted ADR or to a finished milestone or plan; the
release tag keeps the original text. A decision may be superseded by one in another milestone or
an ADR. `rules_check` fails a supersede link whose other record doesn't exist or doesn't link back.
It reads only definition lines and ADR files, so other text that mentions an ID never counts. On a
branch, links may use placeholder IDs; the real numbers replace them in both places before the
merge.

Numbers (operator decision 2026-11-10): on a branch, everyone, people and Codex alike, writes
placeholders: `ADR-NEW`, `OD-NEW`, `P-NEW` (several: `OD-NEW-1`, `OD-NEW-2`). A new ADR file is
`docs/adr/NEW-<slug>.md` titled `# ADR-NEW: ...`; a new plan is `planning-docs/P-NEW-<slug>.md`
with `P-NEW` as its header ID. A decision ID is defined on a line that starts with it and a
colon (after an optional list marker or heading marks): `- OD-NEW-1: <decision> (operator
decision <date>)`. The real numbers are assigned before merging into the default branch: on the
branch, just before the merge, a renamed file in its own pure-rename commit. `rules_check` fails a
pull request into the default branch, or a push to it, that still has a placeholder in one of
those places ("assign numbers before merging"); other branches pass, and text that only mentions
a placeholder never counts (checks README).

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
- ADR or decision line (`OD-<n>`): owns a decision. The plan's Decisions line and the commit name it.
- `CHANGELOG.md`: one line per user-visible change, ending with the plan, ADR or decision ID.
- State file: one pointer per task (plan path, log path, next action), never the content.
- `state-archive/<task>/log.md`: resume card and step detail; links back to the plan.
- When rules move between files, a script checks that every old line maps to new text or an
  approved drop.
