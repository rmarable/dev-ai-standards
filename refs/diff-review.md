# Diff-review brief

Used by the high-stakes add-on before a gate run. Copy this brief to a file, fill the scope line,
and give each reviewer the file's path and its lens. Model and count: high-stakes add-on, Reviews.

## Scope

`<base>...<head>` (exact commits), the plan and IDs it builds, and anything already reviewed and
unchanged (out of scope).

## Lenses

One reviewer per lens unless the size table says otherwise:
1. Correctness: logic, edge cases, error paths, wrong results.
2. Security: secrets, injection, permissions, trust boundaries, data leaving the machine.
3. Reliability and performance: failure handling, retries, resource use, hot paths.
4. Contract risk: public interfaces, data formats, migrations, behaviour users depend on.
5. Tests: missing cases, tests that pass without the fix, weakened checks (H4).

## Rules for the reviewer

- Read-only: no edits, commits, messages to other sessions, services or paid calls.
- Attack, don't summarise. Read the code, not only the diff.
- Report one numbered list, each item:
  `<n>. HIGH | MEDIUM | LOW · confidence high|medium|low · file:line`, then why it matters, a
  failure scenario, and the fix if obvious.
- "Nothing worth fixing" is a valid answer.
- List pre-existing findings (not caused by this diff) apart.
- Write the full output to the file the brief names; return a summary of at most the length the
  brief gives.
- `/code-review` may add a quick pass; it never replaces this review.
