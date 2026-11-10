# Python stack

## Always loaded (`AGENTS.md` block `python`)

- Read `docs/standards/stacks/python.md` before changing tooling, tests, dependencies or CI.

## Toolchain

- Python managed with uv (`.python-version`, `uv.lock`); `uv sync` builds the environment.
- `uv run ruff check .` and `uv run ruff format --check .`.
- `uv run pyright` in strict mode everywhere. Wrap untyped libraries in typed wrappers; each
  suppression names the exact rule.
- `uv run pytest -n auto` (pytest-xdist). Coverage on demand only.
- Enforce package boundaries with import-linter (`uv run lint-imports`).
- `scripts/check` runs these steps in the same order CI does (core).

## Tests

- Tests never call outside services: an autouse fixture makes the real transport raise.
- Tests that touch real system resources (OS secret store, service manager, files outside the
  test's temp folder) use a test prefix and remove what they create.

## Dependencies and licences

- A licence allow-list script runs in CI. Regenerate third-party notices with any lock-file change.

## CI

- Default workflow permissions read-only; each workflow declares its own `permissions:`.
- Actions are pinned to a full commit SHA.
