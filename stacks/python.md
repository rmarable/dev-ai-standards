# Python stack

## Always loaded (`AGENTS.md` block `python`)

- Read `docs/standards/stacks/python.md` before changing tooling, tests, dependencies or CI.

## Toolchain

- Python managed with uv (`.python-version`, `uv.lock`); `uv sync` builds the environment.
- `uv run ruff check .` and `uv run ruff format --check .`. Rules: the kit's
  `docs/standards/templates/ruff.toml` source, rendered by `apply` into `ruff.toml` when the project
  has no Ruff settings (line length 100, ecf's rule set, `docs/standards` excluded). A project with
  its own settings adds `extend-exclude = ["docs/standards"]`.
- `uv run pyright` in strict mode everywhere. Wrap untyped libraries in typed wrappers; each
  suppression names the exact rule.
- `uv run pytest -n auto` (pytest-xdist). Coverage on demand only.
- Enforce package boundaries with import-linter (`uv run lint-imports`).
- `scripts/check` runs these steps in the same order CI does (core); `apply` writes its first
  version, which already runs Ruff, pyright and pytest (`pytest -q`, plus `-n auto` under `--full`;
  "no tests yet" while `tests/` has no test files), so a fresh project passes CI. The pre-commit
  hook runs Ruff on staged `.py` files only.
- `apply` writes `pyproject.toml` when there is none: a virtual uv project (no build-system) named
  after the folder, `requires-python` from the CI minimum, a `dev` group with ruff, pyright, pytest
  and pytest-xdist, `testpaths = ["tests"]`. `new-claude-project` runs `uv lock` before the first
  commit; elsewhere run `uv lock` and commit `uv.lock`, or CI's `uv sync --locked` fails.

## Tests

- Tests never call outside services: an autouse fixture makes the real transport raise.
- Tests that touch real system resources (OS secret store, service manager, files outside the
  test's temp folder) use a test prefix and remove what they create.

## Dependencies and licences

- A licence allow-list script runs in CI. Regenerate third-party notices with any lock-file change.

## CI

- Default workflow permissions read-only; each workflow declares its own `permissions:`.
- Actions are pinned to a full commit SHA.
- Test CI: `apply` writes `.github/workflows/python.yml` from the kit's
  `docs/standards/templates/ci/python.yml` (once; project-owned afterwards): push and pull request,
  docs-only changes skipped, read-only permissions, a matrix of the `requires-python` minimum and
  the latest Python, `uv sync --locked`, then `scripts/check --full`. Path-filtered, so never a
  required check; `rules-check` is the required one.
