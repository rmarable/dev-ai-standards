# A2 fix 1: kit upgrade PRs and the commit-msg hook

Two operator-approved changes (2026-11-10). Tests: 62 pass on Python 3.12.14 and 3.9.6
(`python3 -m unittest discover -s tests`); `./scripts/check` passes.

## Files changed

- `checks/rules_check.py`: kit-upgrade rule. New `kit_findings` (shared with `drift`),
  `upgrade_check`, `is_upgrade_attempt`, `changed_paths`, `project_text`, `semver_key`,
  `standards_version`. A branch uses its own manifest only when every changed path is a kit file
  (under `docs/standards/` or listed in the base or branch manifest), `AGENTS.md` or `CLAUDE.md`
  with only kit-block text and the Standards line changed; the Standards version is strictly newer
  (semver order, prereleases below releases); and the branch's kit text matches its manifest.
  Otherwise: "kit upgrade refused" plus each reason and the usual findings against the base
  manifest. `--base` now also names what an upgrade is compared with, even with `--manifest`.
- `bin/dev-ai-standards`: `apply` installs `.githooks/commit-msg` (executable, runs
  `docs/standards/checks/trailer_check.py --message-file "$1"`) and sets `core.hooksPath .githooks`
  when there is no hooks path, no `.githooks/` and no own hook in `.git/hooks`; otherwise it
  changes nothing and prints the exact line to add. `--dry-run` prints the case. `drift` uses the
  upgrade rule too (otherwise the skill's "run drift again: it must report nothing" step fails on
  every update branch).
- `templates/ci/rules-check.yml`: passes `--base "$BASE_REF"` (the PR base SHA, or
  `origin/<default>` on push) so CI compares an upgrade with the right base.
- `checks/README.md`: "Kit upgrades" replaces "Kit updates"; run line; hook mechanics (the three
  cases, the line to add, dry run, per-clone config).
- `README.md`: apply paragraph names the hook; Update flow step 4 says what an upgrade PR may hold.
- `skills/dev-ai-standards/SKILL.md`: update step 6, same rule.
- `tests/test_upgrade_hooks.py` (new, 9 tests): upgrade passes (default base and CI's
  `--manifest` + `--base`; drift clean); upgrade plus a non-kit file fails; upgrade plus a project
  text edit in `AGENTS.md` fails; same, older and prerelease-of-same versions fail; hook installed
  in a fresh repo (dry run first, then idempotent); existing `core.hooksPath` left alone with the
  line printed; existing `.githooks/` left alone; the installed hook rejects two trailers; no hook
  outside a git repo.

## Choices the brief didn't settle

- Also refuses to install when `.git/hooks` holds a non-`.sample` hook: setting `core.hooksPath`
  would switch it off silently. Stricter than the brief; it prints the line for that folder instead.
- Paths the manifest lists outside `docs/standards/` (today only `.claude/rules/state-file.md`)
  count as kit files, since `apply` owns and hashes them.
- The upgrade rule is tried only when the branch's manifest or Standards version differs from the
  base's and kit text drifted; plain drift still reports as before.
- Consequence: an upgrade PR can't carry its changelog line or apply's other writes
  (`.gitignore`, settings, hook); the docs send them to a separate PR. Operator may prefer to allow
  `CHANGELOG.md`.
- Versions `X.Y` are read as `X.Y.0` (`apply` accepts them in `VERSION`).

## Not done

- The plan (`P001` Part A, check 2: "blocks match `main`'s manifest"; Rules-check workflow line)
  is not edited: it is the operator's spec. It needs one line naming the upgrade exception.
- Projects whose `.github/workflows/rules-check.yml` already exists keep the old copy (apply never
  overwrites it); without `--base`, CI falls back to `origin/main`, then `main`.
- The refusal counts its header line as a problem in "failed (N problem(s))".
