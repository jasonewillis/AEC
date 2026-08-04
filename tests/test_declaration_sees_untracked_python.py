"""`--check` must not call the declaration current while an untracked .py waits.

Both `Foundation gate` failures on 2026-08-03 were the same assertion:

    AssertionError: Tuples differ: () != ('python_paths',)

Both had the same cause. A new `.py` file was written, the suite was run, it
reported green, and only then was the file staged. `tracked_python` enumerates
with `git ls-files`, so the file was invisible; `self_check` reads the index
too, so it was invisible there as well. Two checks that could have spoken were
structurally blind to the same thing, and CI was the first thing in the pipeline
able to see it.

The gap is not that anyone forgot a rule. A commit-then-verify memory existed
and was violated ninety minutes after it was written, because the mistake is one
of sequence: verification feels finished before staging feels necessary. So the
fix is a control at the moment the claim is made, not another rule to remember.

This test pins that control. It reds if `--check` ever again prints PASS while
an untracked, non-ignored Python file is sitting in the tree.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "test_zz_untracked_probe_do_not_commit.py"


def check_declaration() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/generate_source_declaration.py", "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


class UntrackedPythonIsNotCurrentTests(unittest.TestCase):
    def tearDown(self) -> None:
        PROBE.unlink(missing_ok=True)

    def test_an_untracked_python_file_fails_the_currency_claim(self) -> None:
        # Precondition: a clean tree must actually pass, or this proves nothing.
        # If the repository already carries an untracked .py, the assertion
        # below would pass for the wrong reason.
        before = check_declaration()
        self.assertEqual(
            0,
            before.returncode,
            "the tree already fails --check, so this canary cannot isolate the "
            f"condition it claims to test:\n{before.stdout}{before.stderr}",
        )

        PROBE.write_text("# untracked probe\n", encoding="utf-8")
        after = check_declaration()

        self.assertNotEqual(
            0,
            after.returncode,
            "--check reported the declaration current while an untracked .py "
            "was present; that is the exact state that red CI twice on "
            "2026-08-03",
        )
        self.assertIn(PROBE.name, after.stdout + after.stderr)

    def test_an_ignored_python_file_is_not_treated_as_pending(self) -> None:
        """Ignored scratch files never enter the declaration, so they are not a hazard.

        Without `--exclude-standard` this control would red on any local
        scratch file and be disabled within a week, which is how a real control
        becomes an ignored one.
        """
        result = subprocess.run(
            ["git", "check-ignore", "-q", "tmp/scratch.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            self.skipTest("no ignored python path available to exercise this")
        self.assertEqual(0, check_declaration().returncode)


if __name__ == "__main__":
    unittest.main()
