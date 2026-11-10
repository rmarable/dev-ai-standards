{{id}} · Status: draft · Owner: {{owner}} · Created: {{date}} · Updated: {{date}} · Milestone: {{id}} · Tier: {{tier}}

# {{id}}: {{title}}

## Goal

<What is true when this milestone is done, in two or three sentences.>

## Scope

- In: <what this milestone builds>.
- Out: <what it leaves for later, and where that is tracked>.

## Design

<Unbuilt spec text lives here until its step builds it; the step then moves it to the spec.
Code references name the commit they were checked against.>

## Steps

Each step is a short branch merged through the gate; unfinished behaviour stays unreachable.

| Step | Work | Branch | Checks | Status |
|---|---|---|---|---|
| 1 | <work> | <branch> | <what must pass> | not started |

## Verification

<How we will know it works: commands, expected results, real-service tests (go-ahead each time).>

## Decisions

<One line each: "- OD-NEW: <decision> (operator decision YYYY-MM-DD)", or "- OD-NEW: <decision>
(ADR-NEW)". The real number replaces OD-NEW before the merge. A retired decision stays here,
marked "(superseded by OD-<n>, YYYY-MM-DD)" or "(withdrawn, YYYY-MM-DD: <reason>)"; see the
planning add-on.>

## Rejected

<Alternatives turned down, one line each with the reason.>

## Open questions

<One line each, naming who answers.>

## Draft history

- Draft 1, {{date}}: stub created.
