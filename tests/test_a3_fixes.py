"""Tests for the A3 review fixes (K1, K2; operator-approved 2026-11-10).

One test class per area: the upgrade rule and manifest keys (K1-2, K1-5), trailer_check on a
force push (K1-3), gate-status (K1-4, K1-6, K1-12, F1-2), and apply (K1-7, K1-8, K1-10, K1-11,
K2-1 to K2-11). Throwaway repos only; fake `gh` where gate-status needs one.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

from helpers import (
    OUT,
    ZERO,
    GateStatusRunner,
    commit,
    env,
    git,
    init_repo,
    msg,
    py,
    run,
)
from test_apply_rules import KitCase
from test_hooks_lint import load

TRAILER = OUT / "checks" / "trailer_check.py"


def manifest_line(data: bytes, key: str) -> str:
    return f"{hashlib.sha256(data).hexdigest()}  {key}\n"


class UpgradeSet(KitCase):
    """K1-2: purity is decided by a fixed path set, never by the manifest."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(self.repo)
        commit(self.repo, self.home, msg("Apply standards"))
        git(self.repo, self.home, "switch", "-q", "-c", "kit-upgrade")
        (self.kit / "VERSION").write_text("0.2.0\n")
        self.edit(self.kit / "core.md", "1. Don't lie.", "1. Don't lie, ever.")
        self.apply_ok(self.repo)

    def test_pure_upgrade_passes(self) -> None:
        commit(self.repo, self.home, msg("Kit v0.2.0"))
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("kit upgrade v0.1.0 -> v0.2.0", r.stdout)

    def test_k1_reproduction_listing_src_in_manifest_fails(self) -> None:
        evil = b"import os\nos.system('true')\n"
        (self.repo / "src").mkdir()
        (self.repo / "src/app.py").write_bytes(evil)
        mpath = self.repo / "docs/standards/manifest"
        mpath.write_text(mpath.read_text() + manifest_line(evil, "src/app.py"))
        commit(self.repo, self.home, msg("Kit v0.2.0 plus code"))
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("'src/app.py' is not a plain path under docs/standards/", r.stdout + r.stderr)
        self.assertNotIn("using this branch's manifest", r.stdout)

    def test_upgrade_touching_readme_fails(self) -> None:
        commit(self.repo, self.home, msg("Kit v0.2.0 and README"), {"README.md": "hi\n"})
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("(also changed: README.md)", r.stdout)

    def test_bad_manifest_keys_refused(self) -> None:
        rc = load("rc_for_test", OUT / "checks" / "rules_check.py")
        for key in (
            "docs/standards/../../../outside.txt",
            "/etc/passwd",
            "docs\\standards\\x",
            ".claude/rules/other.md",
            "./.claude/rules/state-file.md",
            "docs/standards/manifest",
            "README.md#core",
            "AGENTS.md#nosuch",
            ".github/workflows/x.yml",
        ):
            with self.subTest(key=key):
                self.assertIsNotNone(rc.manifest_key_problem(key))
        self.assertIsNone(rc.manifest_key_problem("docs/standards/refs/honesty.md"))
        self.assertIsNone(rc.manifest_key_problem("CLAUDE.md#state-file"))
        self.assertIsNone(rc.manifest_key_problem(".claude/rules/state-file.md"))  # F1-9


class ManifestEdits(KitCase):
    """K1-5: a manifest change outside an upgrade fails; apply never deletes outside the kit."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(self.repo, "--high-stakes")
        commit(self.repo, self.home, msg("Apply standards"))

    def test_manifest_only_branch_fails(self) -> None:
        git(self.repo, self.home, "switch", "-q", "-c", "sneaky")
        data = b"extra\n"
        (self.repo / "docs/standards/extra.md").write_bytes(data)
        mpath = self.repo / "docs/standards/manifest"
        mpath.write_text(mpath.read_text() + manifest_line(data, "docs/standards/extra.md"))
        commit(self.repo, self.home, msg("Add a manifest line"))
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("kit upgrade refused", r.stdout)

    def test_apply_refuses_traversal_and_deletes_nothing(self) -> None:
        outside = self.tmp / "outside.txt"
        outside.write_text("keep\n")
        mpath = self.repo / "docs/standards/manifest"
        mpath.write_text(mpath.read_text() + f"{'0' * 64}  docs/standards/../../outside.txt\n")
        r = py(
            self.kit / "bin/dev-ai-standards",
            "apply",
            str(self.repo),
            cwd=self.home,
            home=self.home,
        )
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("not a plain path under docs/standards/", r.stderr)
        self.assertTrue(outside.is_file())

    def test_edited_unselected_file_noted(self) -> None:
        (self.repo / "docs/standards/refs/diff-review.md").write_text("edited\n")
        out = self.apply_ok(self.repo)
        self.assertIn(
            "docs/standards/refs/diff-review.md was edited in the project and is no longer"
            " selected",
            out,
        )
        self.assertFalse((self.repo / "docs/standards/refs/diff-review.md").exists())

    def test_state_rule_is_kit_text(self) -> None:  # F1-9
        rule = self.repo / ".claude/rules/state-file.md"
        text = rule.read_text()
        self.assertIn(
            "  .claude/rules/state-file.md\n", (self.repo / "docs/standards/manifest").read_text()
        )
        self.assertNotIn("apply` writes", text, "the meta paragraph stays out of the rule")
        self.assertIn("**Shape:**", text)
        git(self.repo, self.home, "switch", "-q", "-c", "weaken")
        commit(self.repo, self.home, msg("Weaken"), {".claude/rules/state-file.md": "anything\n"})
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(".claude/rules/state-file.md: kit file edited", r.stdout)
        out = self.apply_ok(self.repo)
        self.assertIn(".claude/rules/state-file.md was edited in the project", out)
        self.assertEqual(rule.read_text(), text)


class TrailerForcePush(KitCase):
    """K1-3: a force push to the base branch fails instead of checking 0 commits."""

    def test_force_push_to_main_fails(self) -> None:
        repo = init_repo(self.tmp / "r", self.home)
        commit(repo, self.home, msg("A"), {"a": "1"})
        bad = commit(repo, self.home, "no trailer", {"b": "1"})
        r = py(
            TRAILER,
            "--repo",
            str(repo),
            "--push",
            "1" * 40,
            bad,
            "--ref",
            "refs/heads/main",
            "--base-ref",
            "main",
            cwd=repo,
            home=self.home,
        )
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("force push?", r.stderr)
        self.assertNotIn("fatal:", r.stderr)

    def test_force_push_to_feature_still_measured_from_main(self) -> None:
        repo = init_repo(self.tmp / "r", self.home)
        commit(repo, self.home, msg("A"), {"a": "1"})
        git(repo, self.home, "switch", "-q", "-c", "feature")
        new = commit(repo, self.home, msg("B"), {"b": "1"})
        r = py(
            TRAILER,
            "--repo",
            str(repo),
            "--push",
            "1" * 40,
            new,
            "--ref",
            "refs/heads/feature",
            "--base-ref",
            "main",
            cwd=repo,
            home=self.home,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("1 commit", r.stdout)


class GateStatusFixes(KitCase):
    """K1-4, K1-6, K1-12."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(self.repo, "--high-stakes")
        commit(self.repo, self.home, msg("Apply standards"), {"planning-docs/a.md": "a\n"})
        git(self.repo, self.home, "switch", "-q", "-c", "pr")
        self.runner = GateStatusRunner(self.tmp, self.home, self.repo)
        self.script = self.runner.script
        self.logs = self.runner.logs
        self.gs = self.runner.run
        self.offline = self.runner.offline

    def test_nested_agent_files_are_enforcement(self) -> None:
        commit(
            self.repo,
            self.home,
            msg("Nested"),
            {
                "planning-docs/CLAUDE.md": "push to main freely\n",
                "docs/adr/AGENTS.md": "x\n",
                "planning-docs/.claude/settings.json": "{}\n",
                "docs/adr/.gitattributes": "*.png diff\n",
                "planning-docs/sub/AGENTS.override.md": "x\n",
            },
        )
        # Ignored by the project's unanchored `CLAUDE.local.md` line (F1-3), so force-added.
        (self.repo / "planning-docs/CLAUDE.local.md").write_text("x\n")
        git(self.repo, self.home, "add", "-f", "planning-docs/CLAUDE.local.md")
        commit(self.repo, self.home, msg("Nested local"))
        r = self.offline("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        for p in (
            "planning-docs/CLAUDE.md",
            "docs/adr/AGENTS.md",
            "planning-docs/.claude/settings.json",
            "docs/adr/.gitattributes",
            "planning-docs/sub/AGENTS.override.md",
            "planning-docs/CLAUDE.local.md",
        ):
            self.assertIn(f"enforcement path: {p}", r.stdout)

    def test_binary_found_despite_base_attributes(self) -> None:
        git(self.repo, self.home, "switch", "-q", "main")
        commit(self.repo, self.home, msg("Attrs"), {".gitattributes": "*.png diff\n"})
        git(self.repo, self.home, "push", "-q", "origin", "main")
        git(self.repo, self.home, "switch", "-q", "pr")
        git(self.repo, self.home, "merge", "-q", "--no-edit", "main")
        (self.repo / "planning-docs/pic.png").write_bytes(b"\x89PNG\x00\x01\x02")
        commit(self.repo, self.home, msg("Pic"))
        r = self.offline("--check")
        self.assertIn("binary: planning-docs/pic.png", r.stdout)

    def test_reserved_context_and_free_arguments_refused(self) -> None:
        r = self.offline("--check", "--context", "rules-check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is the CI status", r.stderr)
        for removed in ("--no-fetch", "--list", "--script-path"):  # F1-2: options removed
            r = self.gs("--check", removed, "elsewhere", "--base", "origin/main")
            self.assertEqual(r.returncode, 2, removed)
            self.assertIn("unrecognized arguments", r.stderr)
        r = self.gs("--check", "--base", "origin/widened")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not the PR's base (origin/main)", r.stderr)

    def test_no_fetch_cannot_post(self) -> None:  # F1-2 reproduction
        commit(self.repo, self.home, msg("Plan"), {"planning-docs/b.md": "b\n"})
        head = git(self.repo, self.home, "rev-parse", "HEAD")
        r = self.gs("--docs-only", "--no-fetch", "--base", "main", "--pr-head", head, "--dry-run")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("would run", r.stdout)
        r = self.gs("--docs-only", "--base", "main", "--pr-head", head, "--dry-run")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not the PR's base (origin/main)", r.stderr)

    def test_documented_recipe_runs_base_copy_even_if_branch_copy_is_hostile(self) -> None:
        self.script.write_text("import sys\nprint('gate-status: docs only')\nsys.exit(0)\n")
        commit(self.repo, self.home, msg("Hostile gate-status"), {"src/x.py": "x = 1\n"})
        hostile = self.offline("--check")
        self.assertEqual(hostile.returncode, 0, "a hostile branch copy says what it likes")
        base_copy = self.tmp / "gate-status"
        base_copy.write_text(
            git(self.repo, self.home, "show", "main:docs/standards/bin/gate-status") + "\n"
        )
        r = self.offline("--check", script=base_copy)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("enforcement path: docs/standards/bin/gate-status", r.stdout)
        block = (self.repo / "AGENTS.md").read_text()
        self.assertIn(
            'show origin/main:docs/standards/bin/gate-status > "$TMPDIR/gate-status"', block
        )

    def test_symlink_not_docs_only(self) -> None:  # K1-13 gap
        (self.repo / "planning-docs/link.md").symlink_to("a.md")
        commit(self.repo, self.home, msg("Link"))
        r = self.offline("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("symlink: planning-docs/link.md", r.stdout)

    def test_verify_filters_check_runs_by_name(self) -> None:
        head = git(self.repo, self.home, "rev-parse", "HEAD")
        r = self.offline("--verify", "--operator", "op", "--pr-head", head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log = (self.logs / "gh.log").read_text()
        self.assertIn("statuses?per_page=100", log)
        self.assertIn("check-runs?check_name=local-gate", log)
        r = self.offline(
            "--verify", "--operator", "op", "--pr-head", head, extra={"FAKE_RUNS": "1"}
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("a check run is named 'local-gate'", r.stdout)


class ApplyFixes(KitCase):
    def test_project_standards_line_kept(self) -> None:  # K1-7
        p = self.tmp / "p"
        p.mkdir()
        (p / "AGENTS.md").write_text("# AGENTS.md\n\nStandards: we follow PEP 8.\n")
        self.apply_ok(p)
        text = (p / "AGENTS.md").read_text()
        self.assertIn("Standards: we follow PEP 8.", text)
        self.assertIn("Standards: dev-ai-standards v0.1.0", text)

    def test_import_in_fence_or_comment_does_not_count(self) -> None:  # K1-8
        p = self.tmp / "p"
        p.mkdir()
        self.apply_ok(p)
        claude = p / "CLAUDE.md"
        text = claude.read_text()
        for wrapped in (
            "```\n@AGENTS.md\n```\n",
            "<!--\n@AGENTS.md\n-->\n",
            "~~~md\n@AGENTS.md\n~~~\n",
        ):
            with self.subTest(wrapped=wrapped):
                claude.write_text(text.replace("@AGENTS.md\n", wrapped, 1))
                r = self.rules(p)
                self.assertEqual(r.returncode, 1)
                self.assertIn("does not import AGENTS.md", r.stdout)
        claude.write_text(text)
        self.assertEqual(self.rules(p).returncode, 0)

    def test_promote_quotes_paths(self) -> None:  # K1-10
        p = self.tmp / "my proj;x"
        p.mkdir()
        self.apply_ok(p)
        (p / "docs/standards/refs/honesty.md").write_text("better\n")
        r = py(
            self.kit / "bin/dev-ai-standards",
            "promote",
            "refs/honesty.md",
            str(p),
            cwd=self.home,
            home=self.home,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"cp '{p.resolve()}/docs/standards/refs/honesty.md'", r.stdout)

    def test_bad_settings_shape_fails_cleanly(self) -> None:  # K1-11
        p = self.tmp / "p"
        (p / ".claude").mkdir(parents=True)
        (p / ".claude/settings.json").write_text(json.dumps({"env": "x"}))
        r = py(self.kit / "bin/dev-ai-standards", "apply", str(p), cwd=self.home, home=self.home)
        self.assertEqual(r.returncode, 1)
        self.assertIn("'env' is not an object", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_state_check_hooks_merged(self) -> None:  # K2-1
        p = self.tmp / "p"
        (p / ".claude").mkdir(parents=True)
        mine = {"SessionStart": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}
        (p / ".claude/settings.json").write_text(json.dumps({"hooks": mine}))
        self.apply_ok(p)
        s = json.loads((p / ".claude/settings.json").read_text())
        cmds = [h["command"] for e in s["hooks"]["SessionStart"] for h in e["hooks"]]
        self.assertIn("echo mine", cmds)
        self.assertTrue(any("state_check.py --hook session-start" in c for c in cmds))
        post = s["hooks"]["PostToolUse"][0]
        self.assertEqual(post["matcher"], "Edit|Write")
        self.assertIn("state_check.py --hook post-tool-use", post["hooks"][0]["command"])
        self.assertNotIn("write ", self.apply_ok(p))

    def test_scripts_check_skips_trailer_on_pull_request(self) -> None:  # F2-1
        p = init_repo(self.tmp / "pr", self.home)
        self.apply_ok(p)
        commit(p, self.home, "Merge commit without a trailer\n")
        e = env(self.home)
        e["GITHUB_EVENT_NAME"] = "pull_request"
        r = subprocess.run(
            [str(p / "scripts/check")], cwd=p, env=e, capture_output=True, text=True, check=False
        )
        self.assertIn("skipped trailer_check (HEAD): pull_request", r.stdout)
        self.assertNotIn("trailer_check (HEAD): FAIL", r.stdout)

    def test_scripts_check_written_and_fails_until_edited(self) -> None:  # K2-2, G2
        p = init_repo(self.tmp / "p", self.home)
        self.apply_ok(p)
        sc = p / "scripts/check"
        self.assertTrue(os.access(sc, os.X_OK))
        self.assertNotIn("ruff", sc.read_text())
        self.assertNotIn("<!--", sc.read_text())
        commit(p, self.home, msg("Apply"))
        r = run([str(sc)], p, self.home)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("add your project's steps", r.stdout)
        q = self.tmp / "q"
        q.mkdir()
        self.apply_ok(q, "--stack", "python")
        text = (q / "scripts/check").read_text()
        self.assertIn('"format", "--check"', text)
        self.assertIn('["uv", "run", "ruff"]', text)
        (q / "scripts/check").write_text("mine\n")
        self.apply_ok(q, "--stack", "python")
        self.assertEqual((q / "scripts/check").read_text(), "mine\n")

    def test_kit_rows_added_and_required(self) -> None:  # K2-3
        p = self.tmp / "p"
        p.mkdir()
        (p / "AGENTS.md").write_text("# AGENTS.md\n\nMy rule.\n\n## Overrides\n")
        self.apply_ok(p, "--high-stakes")
        text = (p / "AGENTS.md").read_text()
        for path in (
            "refs/honesty.md",
            "refs/outside-sources.md",
            "checks/README.md",
            "refs/diff-review.md",
        ):
            self.assertIn(f"`docs/standards/{path}`", text)
        self.assertLess(text.index("## Read before you do these"), text.index("## Overrides"))
        self.assertEqual(self.rules(p).returncode, 0)
        (p / "AGENTS.md").write_text(re.sub(r"(?m)^\|.*honesty\.md.*\n", "", text))
        r = self.rules(p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("read-before table has no row for docs/standards/refs/honesty.md", r.stdout)

    def test_existing_adr_and_planning_kept(self) -> None:  # K2-4
        p = self.tmp / "p"
        (p / "docs/adr").mkdir(parents=True)
        (p / "docs/adr/0001-keychain.md").write_text("mine\n")
        (p / "planning-docs").mkdir()
        (p / "planning-docs/PLAN.md").write_text("mine\n")
        out = self.apply_ok(p)
        self.assertFalse((p / "docs/adr/0001-record-architecture-decisions.md").exists())
        self.assertFalse((p / "planning-docs/README.md").exists())
        self.assertIn("already has an ADR 0001", out)

    def test_state_file_block_in_claude_md_only(self) -> None:  # K2-6
        p = self.tmp / "p"
        p.mkdir()
        self.apply_ok(p, "--codex")
        self.assertNotIn("begin state-file", (p / "AGENTS.md").read_text())
        claude = (p / "CLAUDE.md").read_text()
        self.assertIn("begin state-file", claude)
        self.assertIn(
            "exempt from the confirm rule (this standard\n  grants it; no file can)", claude
        )
        self.assertEqual(self.drift(p).returncode, 0)

    def test_codex_block_first_in_existing_project(self) -> None:  # K2-10
        p = self.tmp / "p"
        p.mkdir()
        (p / "AGENTS.md").write_text("# AGENTS.md\n\nMine.\n")
        self.apply_ok(p)
        self.apply_ok(p, "--codex")
        text = (p / "AGENTS.md").read_text()
        self.assertLess(text.index("begin codex"), text.index("begin core"))
        self.assertLess(text.index("Standards: dev-ai-standards"), text.index("begin codex"))
        self.assertEqual(self.drift(p).returncode, 0)

    def test_attributes_written_from_worktree(self) -> None:  # K2-11
        main = init_repo(self.tmp / "main", self.home)
        commit(main, self.home, msg("init"), {"a": "1"})
        wt = self.tmp / "wt"
        git(main, self.home, "worktree", "add", "-q", "-b", "w", str(wt))
        self.apply_ok(wt)
        self.assertIn("CHANGELOG.md merge=union", (main / ".git/info/attributes").read_text())


class LauncherFixes(KitCase):
    """K1-9 (no kit pull under --local) and K1-10 (quoted next steps)."""

    def test_local_does_not_pull_and_quotes(self) -> None:
        upstream = self.tmp / "up.git"
        for args in (
            ["init", "-q", "-b", "main"],
            ["add", "-A"],
            ["commit", "-q", "-m", "kit"],
            ["init", "-q", "--bare", "-b", "main", str(upstream)],
            ["remote", "add", "origin", str(upstream)],
            ["push", "-q", "-u", "origin", "main"],
        ):
            git(self.kit, self.home, *args)
        other = self.tmp / "other"
        git(self.tmp, self.home, "clone", "-q", str(upstream), str(other))
        commit(other, self.home, msg("newer kit"), {"NEW": "1"})
        git(other, self.home, "push", "-q", "origin", "main")
        before = git(self.kit, self.home, "rev-parse", "HEAD")
        src = self.tmp / "my src"
        src.mkdir()
        e = env(self.home)
        e.update(NEW_CLAUDE_PROJECT_ROOT=str(src), GIT_CONFIG_GLOBAL=str(self.tmp / "gc"))
        (self.tmp / "gc").write_text("[user]\n\tname = T\n\temail = t@example.invalid\n")
        r = subprocess.run(
            [sys.executable, str(self.kit / "bin/new-claude-project"), "demo", "--local"],
            env=e,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(git(self.kit, self.home, "rev-parse", "HEAD"), before)
        self.assertIn("Kit not updated", r.stdout)
        self.assertIn(f"cd '{src}/demo'", r.stdout)


__all__ = ["ZERO"]
