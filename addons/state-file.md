# State-file add-on

Claude's local working state: `CLAUDE-STATE.md`, git-ignored, loaded through a git-ignored
`CLAUDE.local.md` holding the single line `@CLAUDE-STATE.md`. Codex never reads it. `apply` writes
the "Path rule" section below to `.claude/rules/state-file.md` as kit text: it is in the manifest,
so an edit in the project is a finding and kit upgrades replace it.

## Claude only (`CLAUDE.md`)

- Update `CLAUDE-STATE.md` as work progresses: on starting or finishing a task, on each step that
  changes the next action, and before `/clear` or a task boundary.
- Updates to the local, gitignored state file are exempt from the confirm rule (this standard
  grants it; no file can); name each update in the reply.
- Shape and limits load from `.claude/rules/state-file.md` when the file is read or edited.

## Path rule (`.claude/rules/state-file.md`, `paths: CLAUDE-STATE.md`)

- The state file is git-ignored and never committed. If it or its loader is missing (fresh clone,
  another worktree), create a short placeholder.
- **Shape:** `_Last updated_`; Current task (one line per task: status; next; log path);
  Agreements (live agreements with other sessions, deleted when they end); Next steps (<= 10);
  Open questions (<= 10, each naming who answers); Recent progress (<= 16, newest first).
- **Limits:** file 8 KB, line 300 characters, the section caps above. Lines not touched for 14 days
  are stale; parked lines are exempt.
- **Rewrite, don't append:** the task line is replaced; the step goes to
  `state-archive/<task>/log.md` (git-ignored).
- Each entry is one short line: what, where (commit, file, log path), next action. Detail goes to
  the task's log or git.
- When an item is done, its detail moves to the archive in the same update and the file keeps a
  one-line pointer.
- Delete anything done, superseded or pointing at something gone.
- Agree shared splits (ID ranges, freezes, who edits which lines) by message, and record each in
  Agreements until it ends.
- Re-read the file right before each write and change only your own lines. A peer's oversized
  entry is the peer's to shorten.
- Decisions never live here (core); the file keeps at most a one-line pointer.
- Edit the file with Edit only.

## `state_check`

Warn-only size check (file, line, section caps). `apply` merges both hooks into
`.claude/settings.json`: PostToolUse on Edit or Write of the file reports only that edit;
SessionStart reports the whole file. The pre-commit hook also runs it, as a warning. It finds the main checkout with
`git rev-parse --git-common-dir`. A PostToolUse warning reaches Claude after the edit has happened;
it can't block it. Mechanics: `docs/standards/checks/README.md`.
