"""Tests for bin/dev-ai-standards (apply, drift, promote) and checks/rules_check.py.

P001 Verification, "Kit": drift after apply reports nothing; it reports an edit in a kit block,
not in project text; overrides are listed; a branch's manifest edit changes nothing; removing
`@AGENTS.md` fails rules_check. Plus the 2026-11-10 interface additions (conditionals,
placeholders, CLAUDE.md blocks, status names).
"""

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from helpers import apply, commit, git, init_repo, make_kit, msg, py


class KitCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.kit = make_kit(self.tmp)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def apply_ok(self, target: Path, *flags: str) -> str:
        r = apply(self.kit, target, self.home, *flags)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def drift(self, target: Path, *flags: str):
        return py(
            self.kit / "bin" / "dev-ai-standards",
            "drift",
            *flags,
            str(target),
            cwd=self.home,
            home=self.home,
        )

    def rules(self, target: Path, *flags: str):
        return py(
            self.kit / "checks" / "rules_check.py", *flags, str(target), cwd=target, home=self.home
        )

    def edit(self, path: Path, old: str, new: str) -> None:
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))


class Apply(KitCase):
    def test_apply_empty_dir_then_drift_reports_nothing(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        self.apply_ok(p)
        r = self.drift(p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("drift: none", r.stdout)
        self.assertEqual(self.rules(p).returncode, 0)

    def test_dry_run_writes_nothing(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        out = self.apply_ok(p, "--dry-run", "--high-stakes", "--codex")
        self.assertIn("would write AGENTS.md", out)
        self.assertEqual(list(p.iterdir()), [])

    def test_second_apply_writes_nothing(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        self.apply_ok(p, "--high-stakes", "--stack", "python")
        out = self.apply_ok(p, "--high-stakes", "--stack", "python")
        self.assertNotIn("write ", out)

    def test_edit_in_kit_block_is_drift_project_text_is_not(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        self.apply_ok(p)
        agents = p / "AGENTS.md"
        self.edit(agents, "## Project\n", "## Project\n\nA project line.\n")
        self.assertEqual(self.drift(p).returncode, 0)
        self.edit(agents, "1. Don't lie.", "1. Don't lie, mostly.")
        r = self.drift(p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("AGENTS.md#core: block edited", r.stdout)

    def test_edit_in_claude_md_block_is_drift(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        self.apply_ok(p)
        manifest = (p / "docs/standards/manifest").read_text()
        self.assertIn("CLAUDE.md#multi-session", manifest)
        self.edit(p / "CLAUDE.md", "(`ListAgents`)", "(`ListAgents`, sometimes)")
        r = self.drift(p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("CLAUDE.md#multi-session: block edited", r.stdout)
        self.assertEqual(self.rules(p).returncode, 1)

    def test_edited_kit_file_is_drift(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        self.apply_ok(p)
        (p / "docs/standards/refs/honesty.md").write_text("changed\n")
        r = self.drift(p)
        self.assertIn("docs/standards/refs/honesty.md: kit file edited", r.stdout)

    def test_conditionals_follow_choices(self) -> None:
        core = self.tmp / "core"
        core.mkdir()
        self.apply_ok(core)
        full = self.tmp / "full"
        full.mkdir()
        self.apply_ok(full, "--high-stakes", "--codex", "--stack", "python")
        for p in (core, full):
            for f in ("AGENTS.md", "CLAUDE.md"):
                text = (p / f).read_text()
                self.assertNotIn("<!-- if ", text)
                self.assertNotIn("<!-- endif -->", text)
        core_text = (core / "AGENTS.md").read_text()
        self.assertNotIn("dev-ai-standards:begin codex", core_text)
        self.assertNotIn("dev-ai-standards:begin high-stakes", core_text)
        self.assertNotIn("refs/diff-review.md", core_text)
        self.assertNotIn("Risk area", core_text)
        self.assertIn("dev-ai-standards:begin other", core_text)
        self.assertNotIn("dev-ai-standards:begin codex", (core / "CLAUDE.md").read_text())
        full_text = (full / "AGENTS.md").read_text()
        for name in ("codex", "high-stakes", "python"):
            self.assertIn(f"dev-ai-standards:begin {name}", full_text)
        self.assertNotIn("dev-ai-standards:begin other", full_text)
        self.assertIn("Risk area", full_text)
        self.assertIn("dev-ai-standards:begin codex", (full / "CLAUDE.md").read_text())
        self.assertIn(
            "Standards: dev-ai-standards v0.1.0 (core, high-stakes, codex; stack python)\n",
            full_text,
        )

    def test_pr_and_no_pr_conditions(self) -> None:
        tmpl = self.kit / "templates" / "AGENTS.md"
        self.edit(
            tmpl,
            "## Overrides\n",
            "<!-- if pr -->\nMerges by PR.\n<!-- endif -->\n<!-- if no-pr -->\nMerges"
            " locally.\n<!-- endif -->\n## Overrides\n",
        )
        a, b = self.tmp / "a", self.tmp / "b"
        a.mkdir()
        b.mkdir()
        self.apply_ok(a)
        self.apply_ok(b, "--no-pr")
        self.assertIn("Merges by PR.", (a / "AGENTS.md").read_text())
        self.assertNotIn("Merges locally.", (a / "AGENTS.md").read_text())
        self.assertIn("Merges locally.", (b / "AGENTS.md").read_text())
        self.assertIn("; no-pr)", (b / "AGENTS.md").read_text())

    def test_placeholders_filled_and_unknown_fails(self) -> None:
        p = self.tmp / "myproj"
        p.mkdir()
        self.apply_ok(p)
        for f in (
            "AGENTS.md",
            "CLAUDE.md",
            "CHANGELOG.md",
            "planning-docs/README.md",
            "CLAUDE-STATE.md",
        ):
            self.assertIsNone(re.search(r"(?<!\$)\{\{", (p / f).read_text()), f)
        self.assertIn("myproj: <what it is", (p / "AGENTS.md").read_text())
        self.assertIn("v0.1.0 (core; stack other)", (p / "CHANGELOG.md").read_text())
        wf = (p / ".github/workflows/rules-check.yml").read_text()
        self.assertIn("${{ github.event_name }}", wf, "GitHub expressions are not placeholders")
        self.edit(self.kit / "templates" / "CHANGELOG.md", "## Unreleased", "## {{nonsense}}")
        q = self.tmp / "q"
        q.mkdir()
        r = apply(self.kit, q, self.home)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown placeholder {{nonsense}}", r.stderr)

    def test_never_overwrites_project_text(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        (p / "CLAUDE.md").write_text("# Mine\n\n@AGENTS.md\n\nMy notes.\n")
        (p / "AGENTS.md").write_text("# AGENTS.md\n\nMy project rule.\n")
        (p / "CHANGELOG.md").write_text("# My changelog\n")
        (p / ".gitignore").write_text("build/\n")
        self.apply_ok(p, "--codex")
        claude = (p / "CLAUDE.md").read_text()
        self.assertTrue(claude.startswith("# Mine\n\n@AGENTS.md\n\nMy notes.\n"))
        self.assertIn("dev-ai-standards:begin codex", claude)
        agents = (p / "AGENTS.md").read_text()
        self.assertIn("My project rule.", agents)
        self.assertIn("dev-ai-standards:begin core", agents)
        self.assertEqual(
            agents.splitlines()[2], "Standards: dev-ai-standards v0.1.0 (core, codex; stack other)"
        )
        self.assertEqual((p / "CHANGELOG.md").read_text(), "# My changelog\n")
        gi = (p / ".gitignore").read_text()
        self.assertTrue(gi.startswith("build/\n"))
        self.assertIn("HANDOFF.md", gi)
        self.assertEqual(self.drift(p).returncode, 0)

    def test_settings_merged_not_replaced(self) -> None:
        p = self.tmp / "p"
        (p / ".claude").mkdir(parents=True)
        (p / ".claude/settings.json").write_text(
            json.dumps({"permissions": {"ask": ["Bash(rm *)"]}, "model": "x"})
        )
        self.apply_ok(p)
        s = json.loads((p / ".claude/settings.json").read_text())
        self.assertEqual(s["model"], "x")
        self.assertIn("Bash(rm *)", s["permissions"]["ask"])
        self.assertIn("Bash(git push *)", s["permissions"]["ask"])
        self.assertNotIn("_comment", s)

    def test_missing_template_fails_clearly(self) -> None:
        (self.kit / "templates" / "CLAUDE.md").unlink()
        p = self.tmp / "p"
        p.mkdir()
        r = apply(self.kit, p, self.home)
        self.assertEqual(r.returncode, 1)
        self.assertIn("template missing from the kit: templates/CLAUDE.md", r.stderr)
        self.assertEqual(list(p.iterdir()), [])

    def test_status_names(self) -> None:
        p = self.tmp / "p"
        p.mkdir()
        self.apply_ok(p, "--high-stakes")
        wf = (p / ".github/workflows/rules-check.yml").read_text()
        self.assertRegex(wf, r"(?m)^  rules-check:\n    #.*\n    name: rules-check$")
        gs = (p / "docs/standards/bin/gate-status").read_text()
        self.assertIn('DEFAULT_CONTEXT = "local-gate"', gs)

    def test_promote_prints_gh_command(self) -> None:
        p = self.tmp / "p"
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
        self.assertIn("gh pr create --repo rmarable/dev-ai-standards", r.stdout)
        self.assertIn("+better", r.stdout)


class RulesCheck(KitCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(self.repo, "--high-stakes")
        commit(self.repo, self.home, msg("Apply standards"))

    def test_pass_and_overrides_listed(self) -> None:
        self.edit(
            self.repo / "AGENTS.md",
            "## Overrides\n",
            "## Overrides\n\n- core: merges stay local (testing doc)\n",
        )
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("manifest: main:docs/standards/manifest", r.stdout)
        self.assertIn("- core: merges stay local (testing doc)", r.stdout)

    def test_missing_import_fails(self) -> None:
        self.edit(self.repo / "CLAUDE.md", "@AGENTS.md\n", "")
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not import AGENTS.md", r.stdout)

    def test_budget(self) -> None:
        self.assertEqual(self.rules(self.repo, "--budget", "100").returncode, 1)

    def test_read_before_path_missing_fails(self) -> None:
        self.edit(
            self.repo / "AGENTS.md",
            "| <project task> | <project file> |",
            "| deploy | `docs/deploy.md` |",
        )
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("read-before table path missing: docs/deploy.md", r.stdout)

    def test_malformed_override_fails(self) -> None:
        self.edit(self.repo / "AGENTS.md", "## Overrides\n", "## Overrides\n\n- nosuchblock: x\n")
        self.assertEqual(self.rules(self.repo).returncode, 1)

    def test_branch_manifest_edit_changes_nothing(self) -> None:
        git(self.repo, self.home, "switch", "-q", "-c", "sneaky")
        agents = self.repo / "AGENTS.md"
        self.edit(agents, "1. Don't lie.", "1. Lie when useful.")
        body = re.search(
            r"<!-- dev-ai-standards:begin core -->(.*?)<!-- dev-ai-standards:end core -->",
            agents.read_text(),
            re.S,
        )
        assert body
        new_hash = hashlib.sha256(body.group(1).encode()).hexdigest()
        mpath = self.repo / "docs/standards/manifest"
        mpath.write_text(
            re.sub(r"(?m)^[0-9a-f]{64}(  AGENTS\.md#core)$", new_hash + r"\1", mpath.read_text())
        )
        commit(self.repo, self.home, msg("Edit core and manifest"))
        r = self.rules(self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("AGENTS.md#core: block edited", r.stdout)
        self.assertIn("manifest: main:", r.stdout)
        self.assertEqual(self.drift(self.repo).returncode, 1)
        mf = self.tmp / "base-manifest"
        mf.write_text(git(self.repo, self.home, "show", "main:docs/standards/manifest") + "\n")
        self.assertEqual(self.rules(self.repo, "--manifest", str(mf)).returncode, 1)


if __name__ == "__main__":
    unittest.main()
