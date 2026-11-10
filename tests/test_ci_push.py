"""Tests for templates/ci/rules-check.yml on push events (K1-1, operator decision 2026-11-10).

The workflow's own `run:` scripts are extracted and run with bash in a clone laid out as GitHub
leaves it: the pushed commit checked out and `origin/main` already at that commit. A push compares
with the commit before the push, so a direct push to main that edits kit text, or replaces the
checker, fails. A forced push to main fails; a push to any other branch, forced or not, compares
with its merge-base with main (F1-1).
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

from helpers import ZERO, commit, env, git, init_repo, msg, run
from test_apply_rules import KitCase

WORKFLOW = Path(__file__).resolve().parent.parent / "templates" / "ci" / "rules-check.yml"


def step_script(name_prefix: str) -> str:
    """The `run: |` body of the first step whose name starts with name_prefix."""
    lines = WORKFLOW.read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip().startswith(f"- name: {name_prefix}"))
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith("- name:"):
            break
        m = re.match(r"(\s*)run: \|$", lines[i])
        if m:
            indent = len(m.group(1))
            body: list[str] = []
            for ln in lines[i + 1 :]:
                if ln.strip() and len(ln) - len(ln.lstrip()) <= indent:
                    break
                body.append(ln)
            return textwrap.dedent("\n".join(body)) + "\n"
    raise AssertionError(f"no run block in step {name_prefix}")


class PushBase(KitCase):
    def setUp(self) -> None:
        super().setUp()
        self.work = init_repo(self.tmp / "work", self.home)
        self.apply_ok(self.work)
        self.c1 = commit(self.work, self.home, msg("Apply standards"))
        self.origin = self.tmp / "origin.git"
        git(self.tmp, self.home, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(self.work, self.home, "remote", "add", "origin", str(self.origin))
        git(self.work, self.home, "push", "-q", "origin", "main")
        shim = self.tmp / "shim"
        shim.mkdir()
        (shim / "python").symlink_to(sys.executable)
        self.path = f"{shim}{os.pathsep}{os.environ.get('PATH', '')}"

    def ci_clone(self, sha: str) -> Path:
        """A clone with the pushed commit checked out and origin/* fetched, as on a runner."""
        ci = self.tmp / f"ci-{sha[:8]}"
        git(self.tmp, self.home, "clone", "-q", str(self.origin), str(ci))
        git(ci, self.home, "checkout", "-q", "--detach", sha)
        return ci

    def run_steps(
        self,
        ci: Path,
        before: str,
        after: str,
        steps: tuple[str, ...] = ("rules_check",),
        ref: str = "refs/heads/main",
        forced: str = "false",
    ):
        rt = self.tmp / f"rt-{after[:8]}-{before[:8]}"
        rt.mkdir(exist_ok=True)
        genv = rt / "github_env"
        genv.write_text("")
        base_env = {
            "PATH": self.path,
            "EVENT": "push",
            "BEFORE": before,
            "AFTER": after,
            "DEFAULT_BRANCH": "main",
            "PUSH_REF": ref,
            "FORCED": forced,
            "PR_BASE_SHA": "",
            "RUNNER_TEMP": str(rt),
            "GITHUB_ENV": str(genv),
        }
        r = self.bash(ci, step_script("Take checks and manifest"), base_env)
        out = r.stdout
        if r.returncode != 0:
            return r
        for line in genv.read_text().splitlines():
            k, _, v = line.partition("=")
            base_env[k] = v
        for name in steps:
            r = self.bash(ci, step_script(name), base_env)
            out += r.stdout
            if r.returncode != 0:
                break
        # All steps' stdout, so the base step's own lines can be checked too.
        return subprocess.CompletedProcess(r.args, r.returncode, out, r.stderr)

    def bash(self, cwd: Path, script: str, extra: dict[str, str]):
        e = env(self.home)
        e.update(extra)
        return subprocess.run(
            ["bash", "-c", script], cwd=cwd, env=e, capture_output=True, text=True, check=False
        )

    def push(self, message: str, files: dict[str, str] | None = None) -> str:
        sha = commit(self.work, self.home, msg(message), files)
        git(self.work, self.home, "push", "-q", "origin", "main")
        return sha

    def reset_manifest_hash(self, key: str, data: bytes) -> None:
        mpath = self.work / "docs/standards/manifest"
        new = hashlib.sha256(data).hexdigest()
        mpath.write_text(
            re.sub(rf"(?m)^[0-9a-f]{{64}}(  {re.escape(key)})$", new + r"\1", mpath.read_text())
        )

    def test_clean_push_to_main_passes(self) -> None:
        c2 = self.push("Docs", {"notes.md": "x\n"})
        r = self.run_steps(self.ci_clone(c2), self.c1, c2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("rules_check: ok", r.stdout)

    def test_direct_push_editing_kit_text_fails(self) -> None:
        agents = self.work / "AGENTS.md"
        agents.write_text(agents.read_text().replace("1. Don't lie.", "1. Lie when useful.", 1))
        body = re.search(
            r"<!-- dev-ai-standards:begin core -->(.*?)<!-- dev-ai-standards:end core -->",
            agents.read_text(),
            re.S,
        )
        assert body
        self.reset_manifest_hash("AGENTS.md#core", body.group(1).encode())
        c2 = self.push("Weaken core")
        r = self.run_steps(self.ci_clone(c2), self.c1, c2)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("AGENTS.md#core: block edited", r.stdout)

    def test_direct_push_replacing_checker_fails(self) -> None:
        fake = b"import sys\nsys.exit(0)\n"
        (self.work / "docs/standards/checks/rules_check.py").write_bytes(fake)
        self.reset_manifest_hash("docs/standards/checks/rules_check.py", fake)
        c2 = self.push("Replace checker")
        r = self.run_steps(self.ci_clone(c2), self.c1, c2)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("docs/standards/checks/rules_check.py: kit file edited", r.stdout)

    def test_unknown_before_fails_closed(self) -> None:
        c2 = self.push("Docs", {"notes.md": "x\n"})
        r = self.run_steps(self.ci_clone(c2), "1" * 40, c2)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("forced push to the default branch (main) is not allowed", r.stdout)

    def test_forced_push_to_default_branch_fails(self) -> None:
        c2 = self.push("Docs", {"notes.md": "x\n"})
        git(self.work, self.home, "reset", "-q", "--hard", self.c1)
        c3 = commit(self.work, self.home, msg("Rewritten"), {"other.md": "y\n"})
        git(self.work, self.home, "push", "-q", "--force", "origin", "main")
        ci = self.ci_clone(c3)
        # GitHub's `forced` flag, and the old tip still fetchable but not an ancestor.
        for forced in ("true", "false"):
            r = self.run_steps(ci, c2, c3, forced=forced)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn("forced push to the default branch (main) is not allowed", r.stdout)

    def test_first_push_to_default_branch_says_so(self) -> None:
        r = self.run_steps(self.ci_clone(self.c1), ZERO, self.c1)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("first push: checked against its own manifest only", r.stdout)

    def feature_push(self, files: dict[str, str] | None = None, *, force: bool = False) -> str:
        sha = commit(self.work, self.home, msg("Feature"), files)
        args = ["push", "-q"] + (["--force"] if force else []) + ["origin", "feature"]
        git(self.work, self.home, *args)
        return sha

    def test_forced_push_to_feature_branch_uses_merge_base(self) -> None:
        git(self.work, self.home, "switch", "-q", "-c", "feature")
        old = self.feature_push({"f.md": "f\n"})
        git(self.work, self.home, "switch", "-q", "main")
        c2 = self.push("Docs", {"notes.md": "x\n"})
        git(self.work, self.home, "switch", "-q", "feature")
        git(self.work, self.home, "rebase", "-q", "main")
        new = git(self.work, self.home, "rev-parse", "HEAD").strip()
        git(self.work, self.home, "push", "-q", "--force", "origin", "feature")
        # The old tip is unreachable after the rebase; the run still passes, against main.
        r = self.run_steps(self.ci_clone(new), old, new, ref="refs/heads/feature", forced="true")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"merge-base with origin/main ({c2})", r.stdout)

    def test_feature_branch_does_not_trust_its_own_earlier_push(self) -> None:
        git(self.work, self.home, "switch", "-q", "-c", "feature")
        fake = b"import sys\nsys.exit(0)\n"
        (self.work / "docs/standards/checks/rules_check.py").write_bytes(fake)
        self.reset_manifest_hash("docs/standards/checks/rules_check.py", fake)
        p1 = self.feature_push()
        p2 = self.feature_push({"g.md": "g\n"})
        r = self.run_steps(self.ci_clone(p2), p1, p2, ref="refs/heads/feature")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn(f"merge-base with origin/main ({self.c1})", r.stdout)
        self.assertIn("docs/standards/checks/rules_check.py: kit file edited", r.stdout)

    def test_new_branch_uses_merge_base(self) -> None:
        git(self.work, self.home, "switch", "-q", "-c", "feature")
        c2 = commit(self.work, self.home, msg("Feature"), {"f.md": "f\n"})
        git(self.work, self.home, "push", "-q", "origin", "feature")
        r = self.run_steps(self.ci_clone(c2), ZERO, c2, ref="refs/heads/feature")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"compared with {self.c1}", r.stdout)

    def test_no_merge_base_fails_closed(self) -> None:
        git(self.work, self.home, "switch", "-q", "--orphan", "other")
        c2 = commit(self.work, self.home, msg("Orphan"), {"o.md": "o\n"})
        git(self.work, self.home, "push", "-q", "origin", "other")
        r = self.run_steps(self.ci_clone(c2), ZERO, c2, ref="refs/heads/other")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no merge-base", r.stdout)

    def test_workflow_lints_shell_files(self) -> None:
        self.assertIn("shell_lint.py --all --require", step_script("ShellCheck"))
        self.assertTrue(
            run(["bash", "-n", "-c", step_script("Take checks")], self.tmp, self.home).returncode
            == 0
        )
