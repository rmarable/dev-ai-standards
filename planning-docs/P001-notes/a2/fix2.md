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

## uv + multi-user round

Operator decisions 2026-11-10: Change A (uv required, Python 3.9 dropped) and Change B (multi-user
readiness). Recorded in P001 Decisions.

### Change A: uv required

- Design: each Python entry point is one file with a POSIX `sh` front. Line 1 is `#!/bin/sh`, then
  PEP 723 inline metadata (`requires-python = ">=3.12"`), then a string that `sh` reads as code:
  `""":"` (to sh, the `:` no-op), a `command -v uv` check that prints exactly "uv is required: brew
  install uv (or see https://docs.astral.sh/uv/getting-started/installation/)" to stderr and exits
  1, then `exec uv run --script "$0" "$@"`. To Python the same lines are the module docstring, and
  the tool's own description follows inside it, so imports stay at the top (no E402).
- Why this and not the alternatives: an `env -S uv run --script` shebang can't print the message
  (env fails first); separate sh wrappers beside `.py` files double the files, break the
  executable-bit-free copies in `docs/standards/` and every test that runs a tool with
  `sys.executable`. One file works as `sh FILE` (hooks, launcher, symlinks in `~/.local/bin`), as
  `./FILE`, and as `python FILE` (CI on an older base, tests). Kit copies lose their mode bits, so
  hooks and the Claude Code hooks call `sh <file>`.
- Covered: `bin/new-claude-project`, `bin/dev-ai-standards`, `bin/gate-status`, `scripts/check`, the
  six `checks/*.py`, `templates/scripts/check`. A test checks the 11 fronts are identical.
- Hooks: `.githooks/*` now `exec sh docs/standards/checks/<check>.py`; Claude Code `state_check`
  commands use `sh`. Re-running `apply` rewrites the old `python3` hooks (`LEGACY_HOOKS`), drops the
  old `python3` settings commands, and notes a `python3 docs/standards/checks/` line in a project's
  own hook. The high-stakes recipe, codex add-on and skill call `sh` too.
- CI: `rules-check.yml` keeps setup-python 3.12 and `python <file>`: the checks come from the base
  commit, which may predate the front; `python` runs both forms, `sh` would fail on an old base.
  `python.yml` unchanged (`uv run python scripts/check --full`). `kit-ci.yml`: setup-python removed,
  matrix 3.12 and 3.13, `sh ./scripts/check --python <version>`.
- `shell_lint` treats a file with the front as Python (not ShellCheck input); kit `scripts/check`
  compiles front files, `sh -n` the plain sh ones (adds `bin/bootstrap`), and runs the unit tests
  with `uv run --no-project --python 3.12`; `--full` runs 3.12 and 3.13 (operator decision
  2026-11-10, same round); `--python X` (repeatable) picks the versions, as kit-ci's matrix does. `VIRTUAL_ENV` from `uv run --script` is dropped for
  child runs (kit and project `scripts/check`).
- 3.9 workarounds removed: `from __future__ import annotations` everywhere, the quoted
  `MetaLookup` alias (now `type` statements), `typing.Callable`, the `tomllib` version guard; Ruff
  target py312, pyright 3.12. `SYSTEM_PYTHON` and the `/usr/bin/python3` test run removed.
- `bin/bootstrap` (POSIX sh): Xcode Command Line Tools (`xcode-select -p`, macOS only), git (the
  `/usr/bin/git` stub doesn't count without the tools, and isn't run), uv; prints install commands;
  offers `brew install uv` after y/N only with a terminal on stdin and stdout and no `CLAUDECODE`.
  Installs nothing else. Exit 0 all present, else 1.
- Tests: a fake `uv` (helpers `FAKE_UV`) is first on every test PATH: it runs `uv run --script FILE`
  on the test's Python, so tests stay offline and never fill a uv cache in the throwaway HOME. The
  launcher's "no uv warns" test is gone (the front stops first); replaced by the front tests.

### Change B: multi-user readiness

- `scripts/setup` (template, written once, executable): `sh docs/standards/bin/bootstrap` (stops
  on failure), then `core.hooksPath .githooks` only when `.githooks/commit-msg` or `pre-commit`
  calls `docs/standards/checks/`, the clone has no `core.hooksPath`, and `.git/hooks` has no
  non-sample hook; otherwise it prints why and the command. `bin/bootstrap` is in `ALWAYS`.
  `apply` also notes "run scripts/setup" when `.githooks/` holds kit hooks but the clone's
  `core.hooksPath` is unset. `gate-status` and checks/README list `scripts/setup` as an
  enforcement path.
- People: template `## People` (before `## Project`): owner and approvers, both `{{owner}}`.
  Owner: `--owner`, else `NEW_CLAUDE_PROJECT_OWNER`, else `git config user.name`, else
  `operator`, with a note for the last two. An existing `AGENTS.md` without `## People` gets the
  section (project text, so it belongs in the second PR of an upgrade, like kit rows). The
  high-stakes "Approvers" line in `## Project` was removed (People holds it).
- core.md Scoped approval: "an approver's own message (`AGENTS.md` People) ... agents act for
  whoever runs the session". 600 words by `wc -w`; cut words, not rules: "Write terse" to "Terse",
  "the affected" to "affected", "right before" to "just before", the Covers line, "and before every
  merge ask" to "and every merge ask", "(the env default doesn't reach them)" to "(env defaults
  don't reach them)". Other "operator" mentions in core (main merges, ruleset) were not asked for
  and are unchanged.
- Numbering: planning add-on (always-loaded block and Naming), codex add-on (placeholder line and
  pick-up step 3), task brief and ADR 0001 templates. `rules_check`: on `main` only, a placeholder
  (`ADR|OD|P-NEW`, optional `-<n>`) in a path or in text of a tracked or untracked file fails.
  Skipped: `docs/standards/**`, the two fixed rules, kit blocks, inline code spans, and in Markdown
  fenced code and HTML comments (quotations). Branch: `--branch`, else in GitHub Actions the pushed
  branch (a pull request is never main), else `git symbolic-ref`. So a PR passes and the push to
  `main` fails: the merger assigns numbers on the branch first.
- `rules_check` also fails when a `.githooks/*` file or `scripts/setup` that the base commit has is
  deleted or emptied.
- CODEOWNERS: `templates/CODEOWNERS` (not copied into `docs/standards/`), written to
  `.github/CODEOWNERS` only when absent: `* @<owner>`, commented out when the owner is the
  `operator` default or not login-shaped; a commented two-approver example.
- README: prerequisites, `bin/bootstrap`, "Joining a project", the paid-plan Limits sentence, the
  new files in the table; the Codex section folded into the `--codex` option (its pilot date and
  `codex exec` stdin note stay in docs/reference.md). docs/reference.md: prerequisites, bootstrap,
  Joining a project, approvals, numbers, `--owner` and `NEW_CLAUDE_PROJECT_OWNER`, files written,
  hooks. CHANGELOG lines added.

### Open points

- The high-stakes recipe now runs the base copy of `gate-status` with `sh`. During the upgrade PR
  that introduces the front, `origin/main` still has the plain-Python copy, and `sh` on it fails
  with a syntax error (loud, not silent); use `uv run --python 3.12 python "$TMPDIR/gate-status"`
  for that one PR.
- Not run: real CI on GitHub (kit-ci, rules-check, python.yml), a vanilla Mac without uv (simulated
  with PATH=/usr/bin:/bin), and the interactive `brew install uv` branch of bootstrap.
- README is 782 words (target about 750).

Results, 2026-11-10: `uv run --python 3.12 python -m unittest discover -s tests` 186 pass (3.12.14),
the same on 3.13.15, 186 pass (was 156; 31 new in `tests/test_a5_fixes.py`, 1 removed). `./scripts/check`
all passed (core.md 600 of 600 words; Ruff format and check; ShellCheck 3 files; tests on 3.12
and 3.13 through uv). Pyright on `checks tests`: 0 errors, 0 warnings. `uvx ruff check` and
`uvx ruff format --check`: clean on `.` and on the extensionless bin/ and scripts/ tools.

Follow-up, same day (operator decision 2026-11-10): `scripts/check` runs the unit tests on 3.12
only; `--full` runs 3.12 and 3.13; kit-ci keeps its matrix (`--python <version>`). The 3.13 suite
was not re-run for this change (186 pass above); the final `./scripts/check` (3.12) result follows.
Final `./scripts/check`: all passed, 186 tests on 3.12 only (no 3.13 run without `--full`); pyright 0 errors; Ruff clean.

## U1 fixes

Operator-approved 2026-11-10 (findings: a3/out/U1.md). New tests in `tests/test_u1_fixes.py`.

- U1-1 HIGH: docs rule plus check. checks/README "Kit upgrades", docs/reference.md step 4, README "Updating", the dev-ai-standards skill step 6, and CHANGELOG all say: when a release changes how scripts or hooks start, the upgrade PR may include `.githooks/*` and `scripts/check`. `rules_check.in_upgrade_set` accepts them (files directly in `.githooks/`, and `scripts/check`) only inside a valid upgrade, so only with a newer Standards version. Tests: upgrade with both passes; same version fails; `.githooks/lib/x.sh` refused. No apply change (operator: no code beyond rules_check).
- U1-2 MED: the recipe is now `d=$(mktemp -d)` ... `uv run --no-project --python 3.12 python "$d/gate-status"` in high-stakes (both places) and checks/README. `--no-project` was added so uv doesn't sync, or refuse on, a project's own requires-python (a deviation from the brief's wording). Text test: no `sh $TMPDIR|$d/gate-status` in docs or skills, recipe present.
- U1-3 MED: fails only in a change to the default branch (PR whose `GITHUB_BASE_REF` is it, push to it, or a local check on it). Default: `--default-branch`, the workflow's `DEFAULT_BRANCH` env (set in templates/ci/rules-check.yml; an env var so an older base copy ignores it), `origin/HEAD`, else the one of main/master that exists; unknown means skipped, with a line saying so. Scans tracked files only: names under `docs/adr/` and `planning-docs/`, the first line of Markdown there, and definition lines (`- OD-NEW: ...`, defined in addons/planning.md "Numbers"). Code spans of any backtick count are stripped; indented code isn't matched. Tests: AGENTS.md prose, CHANGELOG, double-backtick, indented, .py mentions pass; PR with `docs/adr/NEW-foo.md` fails; feature branch, push to a feature branch and PR into another branch pass; push to default fails; untracked not scanned; `master` repo, CI and clone (`origin/HEAD`).
- U1-4 MED: `rules_check.py --people` prints Owner and Approvers from `origin/<default>` (else `<default>`) `:AGENTS.md`, never the working tree. A change to `## People` vs the merge-base warns: "People changed: needs the owner's approval (merge by the owner listed on <default>)", plus a `::warning` annotation in Actions; never fails. core.md Scoped approval: "(`AGENTS.md` People on `main`)". The templates/AGENTS.md People text and the high-stakes Approvers section were updated. codex add-on unchanged (AGENTS.md is already an enforcement path that fails on `codex/*`). CODEOWNERS fixes not done (not in the approved list). Tests: a committed and an uncommitted branch edit are not honoured; the PR warns and passes; no change, no warning.
- U1-5 LOW: the front tries `~/.local/bin`, `~/.cargo/bin`, `/opt/homebrew/bin` and `/usr/local/bin` when `PATH` lacks uv. `DEV_AI_STANDARDS_NO_UV_SEARCH` turns that off (tests need it on machines that have Homebrew uv; documented in reference). All 11 fronts are still identical. Test: uv in `$HOME/.local/bin` with `PATH=/usr/bin:/bin`.
- U1-6 LOW: the front runs `unset UV_PYTHON`. Test: `UV_PYTHON=3.9` doesn't reach uv.
- U1-7 LOW: docs only (checks/README, reference: uv needs a writable cache, `UV_CACHE_DIR`). `~/.cache/uv` was writable from this Claude Code session (2026-11-10). Whether a sandboxed project session allows it is still unverified, so there is no python3 fallback.
- U1-8 LOW: setup_removals also fails on a lost executable bit (base mode 100755) and on a file that no longer mentions `docs/standards/checks/` when the base's copy does. Tests: `chmod -x` and an `exit 0` body.
- U1-9 LOW: core "Covers writes and commits on the step's own branch, and pushing it to the private remote"; "Model map and more:"; core.md 600 words. The People template defines "the operator" as the Owner and the Approvers' roles; the high-stakes Approvers section points to People.
- U1-10 LOW: README Limits has paid plan "(Team or Pro; unverified)", "use public repos" dropped, and "People is a policy, not a login". The approvals sentence says "on `main`". The numbering sentence is now only in reference (with its terms explained). Cuts 1-4 done, plus more to reach 750. Banned-word grep clean.
- U1-11 LOW: setup ends "setup: done, git hooks NOT on (see above)" when it left hooks off, and the hint says the command stops the other hooks. Tests for both cases, and hooks on still ends "setup: done".
- Skipped: U1-1's apply note or rewrite for a `#!/usr/bin/env python3` `scripts/check`, and the settings-command swap in the upgrade set (operator: docs rule only); U1-4's CODEOWNERS changes (not approved).

Results, 2026-11-10: `./scripts/check` all passed (216 tests on 3.12, core.md 600 of 600, Ruff, ShellCheck 3 files). `uv run --no-project --python 3.13 python -m unittest discover -s tests`: 216 pass (3.13.15; was 186). Pyright `checks tests`: 0 errors, 0 warnings. `uvx ruff check` and `format --check`: clean on `.` and on the Python tools in bin/ and scripts/check (bin/bootstrap is sh). `wc -w`: core.md 600, README.md 750.
