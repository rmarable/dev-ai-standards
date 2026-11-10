# A3 fix 2: K1 and K2 findings, plus G1-G4

Operator-approved fixes, 2026-11-10. Tests: 114 pass on Python 3.12.14 and on 3.9.6
(`/usr/bin/python3`), `unittest discover -s tests` (was 62). `./scripts/check` passes (core.md 597
of 600 words; Ruff format and check; ShellCheck 1 file; both test runs). Pyright on `checks`:
0 errors, 0 warnings.

## K1 (code)

- K1-1 HIGH: fixed in `templates/ci/rules-check.yml` (push base = `github.event.before`; zeros:
  merge-base with origin/<default>; none, or `before` missing, fails closed; PR keeps its base) and
  `checks/rules_check.py` (prints the base it compared with; help text). Tests: `tests/test_ci_push.py`
  runs the workflow's own shell steps (direct push editing kit text fails, one replacing the checker
  fails, unknown `before` fails, new branch uses the merge-base, no merge-base fails).
- K1-2 HIGH: fixed in `checks/rules_check.py`: fixed upgrade set (`in_upgrade_set`: `docs/standards/**`,
  `AGENTS.md`, `CLAUDE.md` with only block text and the Standards line); `kit_paths` from manifests
  removed; `parse_manifest` refuses any key outside `docs/standards/**` and the two block-key forms.
  `.claude/rules/state-file.md` left the manifest (written once by `apply`, then project-owned,
  noted when it differs). Tests: K1 reproduction fails, pure upgrade passes, README touch fails, key list.
- K1-3 MED: fixed in `checks/trailer_check.py` (unknown `before` on a push to the base branch fails;
  cat-file stderr silenced). Tests: force push to main fails; feature branch still measured from main.
- K1-4 MED: fixed in `bin/gate-status` (agent files and `.gitattributes` by basename at any depth;
  `.claude`/`.codex`/`.agents`/`.githooks` as any path component; numstat with
  `core.attributesFile=/dev/null --no-textconv`, plus a NUL-byte blob check). Tests: nested files;
  binary found despite a base `*.png diff`.
- K1-5 MED: fixed in `checks/rules_check.py` (key validation; a manifest or Standards change always
  goes through the upgrade rule) and `bin/dev-ai-standards` (removal only inside `docs/standards/`,
  hash compared, edited file noted). Tests: manifest-only branch fails; traversal refused, nothing
  deleted; edited unselected file noted.
- K1-6 MED: fixed in `addons/high-stakes.md` (base-copy recipe in the always-loaded block and the
  Local-gate section) and `bin/gate-status` (`--context rules-check` refused; `--list`/`--script-path`
  only with `--no-fetch`; else `--base` must be `origin/<baseRefName>`). Tests: refusals; the recipe
  gives the base answer when the branch copy is hostile.
- K1-7 LOW: fixed (`set_standards_line` matches `Standards: dev-ai-standards v`). Test added.
- K1-8 LOW: fixed (`has_import` skips fences and HTML comments). Test added.
- K1-9 LOW: fixed in `bin/new-claude-project` (no pull under `--local` or no human; prints the
  command; docstring says the human check is a reminder). Test added.
- K1-10 LOW: fixed (`shlex.quote` in promote and launcher printed commands). Tests added.
- K1-11 LOW: fixed (non-object settings values and a failed `git config` give a one-line error).
  Test added.
- K1-12 LOW: fixed (`statuses?per_page=100`, `check-runs?check_name=<context>`, `total_count`).
  Test with fake gh.
- K1-13 LOW: fixed (launcher tests wrap the real apply with a logger, so the `apply.log` checks can
  fail). Added the missing cases: own `.git/hooks` hook, `--verify`, symlink, trailer force push,
  upgrade listing a non-kit path, manifest-only PR. Copy detection: git finds a copy only when its
  source changes in the same diff, and P001 allows docs-to-docs copies, so no copy test was added.
- K1-14 LOW: fixed in `scripts/check` (also runs the tests under `/usr/bin/python3`, with a visible
  skip line when it is missing) and `checks/README.md` (3.9 to 3.12). Test: file list.

## K2 (docs)

- K2-1 MED: fixed (`apply` merges both `state_check` hooks into `.claude/settings.json`; the Codex
  line says the skill installs its hook; README, launcher and apply print that step). Test added.
- K2-2 MED: fixed (`templates/scripts/check`, written once and executable; it fails until edited).
  Test added.
- K2-3 MED: fixed (`apply` adds missing kit rows; `rules_check` fails without them). Test added.
- K2-4 MED: fixed (no ADR NNNN if `docs/adr/NNNN-*` exists; no planning index if `planning-docs/`
  has files). Test added.
- K2-5 MED: fixed in README (Prerequisites, Environment, clone command, Codex step, PATH form);
  launcher comments name the variables. Owner default unchanged (documented instead).
- K2-6 MED: fixed (state-file block now under "Claude only" with the operator's wording; dropped
  from the AGENTS template). Core pointer skipped: it would make core 603 words (cap 600).
- K2-7 LOW: fixed (multi-session block: "Codex: ask the operator instead").
- K2-8 LOW: fixed (P001 Verification line reworded).
- K2-9 LOW: fixed (`docs/standards/` prefixes in core, codex and high-stakes add-ons).
- K2-10 LOW: fixed (codex block inserted first; core headings demoted one level, same word count).
  Test added.
- K2-11 LOW: fixed (`git rev-parse --git-common-dir`). Test from a linked worktree.
- K2-12 LOW: skipped. It gives no concrete fix: the header lines are the operator's spec, the tag
  name is an open W2 question, and the reviewer calls the em dashes fine.

## Operator additions

- G1 gitignore: base list (agent files, secrets, `.DS_Store`) plus `templates/gitignore-python`
  and `-iac`; append-only merge under `# dev-ai-standards`, listed in the dry run; kit `.gitignore`.
  Agent-file lines are now root-anchored (`/CLAUDE-STATE.md`): unanchored, they ignored the kit
  copy `docs/standards/templates/CLAUDE-STATE.md`, which CI then saw as missing. Tests added.
- G2 ruff: `templates/ruff.toml` (`{{python_target}}` from `requires-python`, else py312; excludes
  `docs/standards`), written only with no Ruff settings and never copied into `docs/standards/`
  (an unrendered placeholder breaks Ruff). Project `scripts/check` runs Ruff (uv, else ruff, else
  fails). stacks/other and stacks/python updated. Kit `ruff.toml` (py39); kit code formatted and
  clean. Fixes: explicit `check=False`, long lines split, https-only `GITHUB_API_URL`. Named
  `noqa` on 10 long command functions (PLR0911/0912/0915), `S606` (exec claude), `S310`, one
  `PLC0415`. Tests added.
- G3 pre-commit: `checks/pre_commit.py` and `checks/secret_scan.py`; installed with commit-msg
  under the same rule. It never runs tests or `scripts/check`. Codex add-on and skill: run
  `scripts/check` and `secret_scan --staged` before the hooks-off commit. Docs in checks/README
  and README. Tests use runtime-built fake keys, including one proving no tests or
  `scripts/check` run.
- G4 shellcheck: `checks/shell_lint.py` (by `.sh` and shebang), run by the project
  `scripts/check`, the pre-commit hook (staged only), CI (`--require`; preinstalled-on-runner
  unverified until A4) and the kit `scripts/check`. The Codex hook moved to
  `templates/hooks/codex-handoffs.sh` (ShellCheck clean); skill v3. Tests added.

## Choices to review

- The push that creates the default branch has no earlier commit, so its merge-base is itself and
  that one run checks the commit against its own manifest. It does not fail closed.
- Test commits use `--no-verify`: fixtures build bad states on purpose, and the hooks have their
  own tests.
- The `state-file.md` path rule is project-owned after its first write, so its edits aren't
  detected. A kit change to it reaches projects only through a separate PR.

## Fix round 3 (F1)

- F1-1 MED: fixed (rules-check: forced push to the default branch fails, by `forced`, an unknown `before` or a non-ancestor `before`; any other branch or tag uses its merge-base with the default branch). Tests: forced push to main both ways, rebased feature force push passes, feature branch ignores its own weakened earlier push, first push message.
- F1-2 MED: fixed by removal (`--no-fetch` gone; `--list` and `--script-path` too, since they existed only for it). Tests run offline with a fake `gh` and a local bare `origin`; posting with `--no-fetch` exits 2.
- F1-3 MED: fixed (kit template renamed `templates/CLAUDE-STATE.template.md`; kit gitignore lines unanchored again). Test: a project ignore `CLAUDE-STATE.md` doesn't hide the kit copy; `git add -A` takes it and rules_check passes.
- F1-4 MED: fixed (hunk-aware parser with counts; `+++ ` a header only outside hunks; fixed `a/` `b/` prefixes; bytes decoded without newline translation; output file and line only). Tests: F1's reproduction, every pattern in 7 line shapes never printed, parser unit test, noprefix/mnemonicPrefix.
- F1-5 MED: fixed (zsh files print "zsh: not checked: <path>"; `dash`, `ksh`, `env -S` and `.bash` added). Test.
- F1-6 MED: fixed in the hook (`ruff` on PATH, else `.venv/bin/ruff`, else "ruff not found: skipped"; never `uv run`). `scripts/check` template keeps `uv run`. Tests for all three, uv never called.
- F1-7 LOW: fixed (apply's note says to add `extend-exclude = ["docs/standards"]`; template `scripts/check` passes `--extend-exclude docs/standards`).
- F1-8 LOW: fixed (note names the security fix and says to replace the workflow in a separate PR; checks/README states the direct-push workflow bypass).
- F1-9 LOW: fixed (`.claude/rules/state-file.md` is one fixed manifest key and in the upgrade set; apply rewrites it with an edited-file note; meta paragraph moved out of the copied section). Test.
- F1-10 LOW: fixed (first push to the default branch prints "first push: checked against its own manifest only (no earlier commit)"). Launcher-subject requirement not added (optional in F1). Test.
- F1-11 LOW: fixed (during a valid upgrade a missing kit-row path is an info line, not a failure; outside an upgrade it still fails). Test.
- F1-12 LOW: fixed by wording (hook docstring and checks/README: staged names, working-tree content; only the secret scan reads the index).
- F1-13 LOW: fixed (`--all` uses `git ls-files --cached --others --exclude-standard`; tree walk outside git). Test.
- F1-14 LOW: fixed (GITHUB_API_URL error inside main's try: one-line error, exit 2; noqa reason added). Test.
- Test plumbing: fake `gh` and runner moved to tests/helpers.py; `PreCommitBase` split out; `pyrightconfig.json` (extraPaths tests, Python 3.9).
- "Choices to review" above: the state-file entry is superseded by F1-9.

## G5 test CI

- `templates/ci/python.yml`: written once by `apply --stack python` to `.github/workflows/python.yml`; push and pull_request with docs-only `paths-ignore`; read-only; concurrency with cancel-in-progress; ubuntu-24.04; matrix `{{python_min}}` (requires-python, default 3.12) and `{{python_latest}}` (3.13, or the minimum if newer; one entry when equal); `uv sync --locked`, then `uv run python scripts/check --full` (`python` added: whether `uv run` runs an extensionless script directly is unverified).
- Template `scripts/check` (python): pyright, and with `--full` `pytest -n auto`, through uv.
- Kit `.github/workflows/kit-ci.yml`: no path filter, read-only, Python 3.9 and 3.12 (3.9 on ubuntu-24.04 unverified until A4), setup-uv for `uvx ruff`, ShellCheck installed with apt when missing (clear failure if that fails), then `./scripts/check`.
- `astral-sh/setup-uv` SHA is a placeholder (40 zeros): no network to look it up; both files say so next to `TODO pin: verify at A4`.
- stacks/python.md points to the template; stacks/other.md has the pattern line; README mentions both. Tests: python stack fills placeholders (3.11/3.13, single 3.13, default 3.12/3.13); other and iac don't install it; text checks of both files.

## A4 pilot fixes

Two bugs from the live pilot, 2026-11-10 (operator-approved).

- Stale failure summary: `bin/new-claude-project` printed "git repo in ... (branch main, no commits
  yet)" beside "first commit c8f3304 on main" after a later ruleset 403. `Run.report` now computes
  the repo line when it prints (`git symbolic-ref`, `git rev-parse --verify -q --short HEAD`); the
  separate commit line is gone. Tests: a fake `gh` whose ruleset call fails (422) after repo create;
  the summary shows `commit <sha>` and not "no commits yet"; a declined run still says "no commits
  yet".
- GitHub Free ruleset 403 (stderr has "403" and "upgrade" or "public"): warning "GitHub Free: no
  ruleset on a private repo; protection is CI plus the reminders", no further rulesets tried, then
  Claude opens or next steps print, exit 0. Any other ruleset failure (including another 403) still
  stops. Tests for both.
- Python CI failed on "No pyproject.toml found": `templates/pyproject.toml` (virtual uv project:
  name from the folder, normalized; `version = "0.1.0"`; `requires-python = ">={{python_min}}"`;
  `dependencies = []`; dev group ruff, pyright, pytest, pytest-xdist; `testpaths = ["tests"]`; no
  build-system) written by `apply --stack python` only when absent, else a note. In `NOT_COPIED`
  like `ruff.toml` (an unrendered `{{python_min}}` is not a valid specifier). The launcher runs
  `uv lock` after apply and the M1 stub, before the file list and the commit; without uv, or if
  `uv lock` fails, it warns that CI's `uv sync --locked` fails until `uv lock` runs. Tests: fake
  `uv` logs `lock` and `uv.lock` is in the first commit; no uv on PATH warns.
- Python-stack `scripts/check` template: `TODO = False`; pyright, then `pytest -q` (plus `-n auto`
  under `--full`) only when `tests/` has `test_*.py` or `*_test.py`, else "no tests yet" and pass.
  Each tool via `uv run <tool>`, else the tool on PATH, else a FAIL line. K2-2's intent kept for
  `other` and `iac`: `TODO = True` and the "add your project's steps" failure, since the kit can't
  know their steps. python.yml unchanged in steps (`uv sync --locked`, `scripts/check --full`); its
  comments now say where `pyproject.toml` and `uv.lock` come from. Tests: fresh python project
  passes with fake ruff/pyright/pytest and no uv; pytest runs `-q` / `-q -n auto` with a test file;
  other and iac still fail.
- Checked by hand with the real uv (network), not in the suite: fresh `apply --stack python`,
  `uv lock`, commit, `uv sync --locked`, `uv run python scripts/check --full` all passed (Python
  3.15.2 picked by uv); with a test file, pytest passed too.

## Doc rules

Operator-approved 2026-11-10.

- `refs/user-docs.md` (U1-U6: audience, voice, banned words, shape, accuracy, terms), in `ALWAYS`,
  so it is a kit file in the manifest. core.md unchanged.
- `.claude/rules/user-docs.md` written like `.claude/rules/state-file.md`: a second fixed manifest
  key (`rules_check.FIXED_RULES`), in the upgrade set, rewritten on each apply with an edited-file
  note. Frontmatter `paths: ["README.md", "docs/**"]`; `docs/standards/**` is excluded in the body
  only, since no exclusion form for `paths` was verified (unverified whether one exists).
- Read-before row (template and `KIT_READ_BEFORE`, so `apply` adds it to existing tables and
  `rules_check` requires it): edit `README.md` or `docs/**` (not `docs/standards/**`) ->
  `docs/standards/refs/user-docs.md`.
- checks/README updated (upgrade set, manifest format). Tests: rule file, manifest keys, row in new
  and existing AGENTS.md, drift catches edits to the ref and to the rule.
- Kit README replaced and `docs/reference.md` added from the supplied drafts, then updated for the
  A4 fixes (scripts/check row, python `pyproject.toml` and `uv.lock`, the Free 403 warning; in the
  reference also the uv prerequisite, launcher steps, what apply writes, the user-docs rule, kit-owned
  text and the upgrade set). README 687 words (wc -w). Banned-word grep clean (the only hits:
  `operator`, the literal `--owner` default; `P001` in a link path). Flags checked against `--help`
  of new-claude-project, apply, drift and promote.

Results (A4 pilot fixes and doc rules together), 2026-11-10: `unittest discover -s tests` 156 pass
on Python 3.12.14 and on 3.9.6 (`/usr/bin/python3`), 15 new. `./scripts/check` passes (core.md 597
of 600 words; Ruff format and check; ShellCheck 1 file; both test runs). Pyright on `checks tests`:
0 errors, 0 warnings.
