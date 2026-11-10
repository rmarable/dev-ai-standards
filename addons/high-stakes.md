# High-stakes add-on

For projects where a wrong result costs money, data or trust. The project names its risk area and
its approvers in its own `AGENTS.md` text; this file never names a project.

## Always loaded (`AGENTS.md` block `high-stakes`)

- **Phase R:** every plan that changes the project's named risk area gets Phase R (read-only
  reviewers) before it is built; a diff review before a gate run.
- Every merge to `main` runs the full gate; it passes only with 0 skipped (fix the environment,
  don't merge).
- Read `docs/standards/addons/high-stakes.md` before a review, a gate run, a release, a
  real-service test or heavy shared work.
- Run `gate-status` only as the base branch's copy, never the checkout's, and always through
  `uv run`, never `sh` (an older base copy is plain Python): `git fetch origin && d=$(mktemp -d)
  && git show origin/main:docs/standards/bin/gate-status > "$d/gate-status" && uv run
  --no-project --python 3.12 python "$d/gate-status" <args>`.

## Reviews

- **Sizes** (reviewer count): 1 trivial or single-file fix; 2 small, contained change; 4 plan
  changing core behaviour; 8 major release; 12 or 16 milestone design, architecture or
  trust-boundary change. The brief states the count and lenses; the operator confirms. An agent
  never proposes fewer than the table gives.
- **Models:** Opus by default for every review (Phase R, diff, delta and fix checks, blind checks).
  Fable only for big-picture rounds (milestone design or architecture, trust boundary or threat
  model, major release Phase R) at sizes 1 to 8; sizes 12 and 16 Opus only. When Fable is out of
  credits, run the round on Opus and say so in the findings. Sonnet never reviews.
- **How a round runs:** reviewers run in parallel, read-only, told to attack, not summarise, and to
  cite `file:line`. Findings are merged into one numbered list by severity, key claims are
  spot-checked against the code, the operator decides each, and the plan is re-drafted. Raw output
  goes to `state-archive/<task>/`; the plan gets one line per round.
- **Diff review:** before a gate run, using `docs/standards/refs/diff-review.md`. `/code-review`
  may add a quick pass, never replace one.
- **Fix checks** review only the diff since the last review; one full review of the branch before
  merge. A round that finds only lows: fix them with tests; the next scheduled review confirms them.
- While a review is pending, results aren't final: run affected tests only; one full run after the
  last review.
- Never offer lighter, skipped, frozen or deferred reviews; review every fix round until no high or
  medium remains.
- Claude runs every review. Subagents get read-only work unless the operator says otherwise; each
  prompt says so.

## Writing and fixing rules

- Where stakes are high, check every rule against the code and data before writing it, and say
  what was checked.
- Test a reviewer's recommendation against the data before folding it in; before review, run new
  rules against the plan's own fixtures.
- Prove each new test fails without its fix; check each fix against the code before writing it.
- Before loosening a safety check, measure how often it fires and try the upstream fix.
- **Fix loop (ground truth before models):** cut scope first; build a ground-truth table of every
  real call, with its source; fix the checker; fix lists remove more than they add; one reviewer
  attacks the list; model one area at a time; prose last.
- **Stop rule:** when new highs come from the last round's fixes, or review keeps finding new holes,
  stop patching and ask the operator. Change the shape so whole classes of fault vanish, model it
  exhaustively with past bugs seeded, and write prose last.

## Model checks

- In a model-checked design, every rule has a model event and a seeded fault that fails without
  it; no "not modelled" or "superset" claim for anything that decides whether work can finish.
- Keep a rule-to-model table; each rule has one owning paragraph that others cite by name.
- A script checks the plan against the models (names, faults, counts, cited IDs) and passes before
  each review round.
- Run long CPU-bound checks in parallel under a memory budget sized by measured peaks, after the
  active sessions have said OK (below).

## Shared machine

Ask active sessions and wait for their OK before heavy shared work; standing budgets agreed between
sessions still apply without asking. If a peer doesn't answer, tell the operator.

## Gate

- The gate is the project's full test run. Record its result (N passed, 0 skipped, platform, date)
  in the merge message or the local-gate status.
- A version bump runs the full suite.
- **Docs only** skips the gate. The docs-only list is project-owned path prefixes, never
  extensions, read from the base branch. It excludes code, tests, packaged data, prompts, eval data
  and any file a test reads. Both sides of every rename are checked. The kit's default list is
  narrow.

## Local-gate status (PR projects with a local gate)

- Required, with up-to-date branches. Only Claude posts it, through `docs/standards/bin/gate-status`,
  always the base branch's copy, never the checkout's, run with `uv run`: `git fetch origin &&
  d=$(mktemp -d) && git show origin/main:docs/standards/bin/gate-status > "$d/gate-status" && uv
  run --no-project --python 3.12 python "$d/gate-status" --check` (then `--docs-only` or
  `--passed N --skipped 0`).
- The script and the docs-only list are always read from the base branch (`origin/main`, after
  `git fetch`), never from the PR's branch; the PR head can't change either.
- Docs only is decided on `git diff --no-renames --raw origin/main...HEAD` (or `--name-status -M`
  reading both sides), so the old and new path of every rename are checked. Copies, binaries,
  submodules, symlinks and deletions are docs only only if every path involved is on the list.
- Docs only: success "docs only, no <gate> gate". Otherwise only after the real full run, on a
  clean tree with `HEAD` equal to the PR head: "N passed, 0 skipped".
- Before the merge ask, `gate-status --verify` (same base copy) checks the status's creator is the operator's
  login and no check run has its name.

## Real-service tests

Run only on the operator's go-ahead, each time, with throwaway code kept out of the repo and
everything they create removed afterwards; results are recorded in the spec. Plans give each one
its own step.

## Releases and tags

- Milestone tags mark internal progress only; only release tags are built and published.
- Before any release, bump or release tag, follow the project's release procedure.
- Choose a fast or checked release by what it changes (migrations, upgrade or rollback code, data
  formats). A checked release builds locally and tests upgrade, rollback and upgrade before tagging.
- At tagging, the next-release changelog heading becomes the tag name and date; no new lines go
  under a dated heading.

## Approvers

The Approvers in `AGENTS.md` People, as the default branch has it, approve `main` merges, tags and
rule changes; "the operator" is People's Owner. A People change counts only once merged by the
owner (rules-check warns on it). Team repos (two or more humans): one human approval, and
`CODEOWNERS` on the enforcement paths and on `## Overrides`.
