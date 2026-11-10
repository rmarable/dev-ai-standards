"""Tests for record IDs and retired decisions (planning add-on, "IDs" and "Retiring a decision").

rules_check fails a supersede link that points at no record or has no link back, an ID defined
twice, and a file added under planning-docs/ without an ID. Existing planning files are never
checked, and text outside definition lines and ADR files never counts.
"""

from pathlib import Path

from helpers import commit, git, init_repo, msg
from test_apply_rules import KitCase

OLD = "- OD-3: use pip (operator decision 2026-11-01) (superseded by OD-9, 2026-11-10).\n"
NEW = "- OD-9: use uv (operator decision 2026-11-10). Supersedes OD-3.\n"
PLAN_HEAD = "P002 · Status: draft · Owner: o · Created: 2026-11-10\n\n# P002: cache\n"


class RecordCase(KitCase):
    def branch(self) -> Path:
        """An applied project on a feature branch, passing rules_check."""
        repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(repo)
        commit(repo, self.home, msg("Apply standards"))
        git(repo, self.home, "switch", "-q", "-c", "feature")
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return repo

    def check(self, files: dict[str, str]):
        repo = self.branch()
        commit(repo, self.home, msg("Records"), files)
        return self.rules(repo)


class DecisionLinks(RecordCase):
    def test_two_way_link_passes(self) -> None:
        r = self.check({"SPEC.md": f"# Spec\n\n{OLD}{NEW}"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_link_across_files_passes(self) -> None:
        r = self.check(
            {
                "planning-docs/milestones/M1-a.md": f"M1 · Status: done\n\n{OLD}",
                "planning-docs/milestones/M2-b.md": f"M2 · Status: draft\n\n{NEW}",
            }
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_missing_back_link_fails(self) -> None:
        r = self.check({"SPEC.md": f"# Spec\n\n{OLD}- OD-9: use uv.\n"})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(
            'OD-3 superseded by OD-9, but OD-9 (SPEC.md:4) doesn\'t say "Supersedes OD-3"', r.stdout
        )

    def test_missing_forward_link_fails(self) -> None:
        r = self.check({"SPEC.md": f"# Spec\n\n- OD-3: use pip.\n{NEW}"})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(
            'OD-9 supersedes OD-3, but OD-3 (SPEC.md:3) doesn\'t say "superseded by OD-9"', r.stdout
        )

    def test_undefined_target_fails(self) -> None:
        r = self.check({"SPEC.md": f"# Spec\n\n{OLD}"})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("SPEC.md:3: OD-3 superseded by OD-9, which isn't defined", r.stdout)

    def test_duplicate_definition_fails(self) -> None:
        r = self.check(
            {"SPEC.md": "- OD-4: a.\n", "planning-docs/P002-x.md": f"{PLAN_HEAD}\n- OD-4: b.\n"}
        )
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("OD-4 is defined 2 times", r.stdout)

    def test_marker_on_continuation_line_counts(self) -> None:
        old = (
            "- OD-3: use pip, a long line that wraps\n"
            "  onto the next (superseded by OD-9, 2026-11-10).\n"
        )
        r = self.check({"SPEC.md": f"# Spec\n\n{old}{NEW}"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_prose_mention_ignored(self) -> None:
        r = self.check({"NOTES.md": "OD-3 was superseded by OD-9 last week.\n"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_placeholder_link_on_branch_passes(self) -> None:
        old = "- OD-3: use pip (superseded by OD-NEW-1, 2026-11-10).\n"
        new = "- OD-NEW-1: use uv. Supersedes OD-3.\n"
        r = self.check({"SPEC.md": f"# Spec\n\n{old}{new}"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_adr_links(self) -> None:
        old = "# ADR 0002: pip\n\n- Status: superseded by ADR-0003\n"
        new = "# ADR 0003: uv\n\n- Status: accepted\n\nSupersedes ADR 0002.\n"
        r = self.check({"docs/adr/0002-pip.md": old, "docs/adr/0003-uv.md": new})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_adr_one_way_fails(self) -> None:
        old = "# ADR 0002: pip\n\n- Status: superseded by ADR-0003\n"
        new = "# ADR 0003: uv\n\n- Status: accepted\n"
        r = self.check({"docs/adr/0002-pip.md": old, "docs/adr/0003-uv.md": new})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(
            "ADR-2 superseded by ADR-3, but ADR-3 (docs/adr/0003-uv.md:1) doesn't say"
            ' "Supersedes ADR-2"',
            r.stdout,
        )


class PlanIds(RecordCase):
    def test_plan_with_id_passes(self) -> None:
        r = self.check(
            {
                "planning-docs/P002-cache.md": PLAN_HEAD,
                "planning-docs/P003-db/README.md": "P003 · Status: draft\n",
                "planning-docs/P003-db/step-1.md": "# Step 1\n",
                "planning-docs/P002/codex-x.md": "P002 · Codex task brief\n",
                "planning-docs/milestones/M2-api.md": "M2 · Status: draft\n",
                "planning-docs/releases/v1.2.0-cut.md": "v1.2.0 · Status: draft\n",
                "planning-docs/P-NEW-later.md": "P-NEW · Status: draft\n",
            }
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_file_without_id_fails(self) -> None:
        r = self.check({"planning-docs/notes.md": "# Notes\n", "planning-docs/misc/a.md": "# A\n"})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(
            "planning-docs/notes.md: no ID in the name (name it P<nnn>-<slug>.md", r.stdout
        )
        self.assertIn(
            "planning-docs/misc/a.md: the folder misc/ doesn't start with a plan ID", r.stdout
        )

    def test_first_line_mismatch_fails(self) -> None:
        r = self.check(
            {
                "planning-docs/P002-cache.md": "# Cache plan\n",
                "planning-docs/P003-db/README.md": "P030 · Status: draft\n",
                "planning-docs/milestones/M2-api.md": "M20 · Status: draft\n",
            }
        )
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(
            "planning-docs/P002-cache.md:1: the first line must start with its ID, P002", r.stdout
        )
        self.assertIn(
            "planning-docs/P003-db/README.md:1: the first line must start with its ID, P003",
            r.stdout,
        )
        self.assertIn(
            "planning-docs/milestones/M2-api.md:1: the first line must start with its ID, M2",
            r.stdout,
        )

    def test_existing_file_without_id_passes(self) -> None:
        repo = init_repo(self.tmp / "repo", self.home)
        self.apply_ok(repo)
        commit(repo, self.home, msg("Apply standards"), {"planning-docs/old-notes.md": "# Old\n"})
        git(repo, self.home, "switch", "-q", "-c", "feature")
        commit(repo, self.home, msg("Edit"), {"planning-docs/old-notes.md": "# Old, edited\n"})
        r = self.rules(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_untracked_file_is_checked(self) -> None:
        repo = self.branch()
        (repo / "planning-docs/draft.md").write_text("# Draft\n")
        r = self.rules(repo)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("planning-docs/draft.md: no ID in the name", r.stdout)
