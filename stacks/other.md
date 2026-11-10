# Other stack

For projects that are neither Python nor IaC, or are mixed. The kit adds no toolchain rules.

## Always loaded (`AGENTS.md` block `other`)

- This project's toolchain, test and lint commands are listed in its own `AGENTS.md` text, and
  `scripts/check [--full]` runs them exactly as CI does (core).

## What the project fills in

- The commands for build, lint, type check and tests, and which of them are "affected only" while
  working and which make the full suite (core).
- Where secrets live (core: a secret store only).
- If the project grows into Python or IaC, re-run `apply` with that stack.
