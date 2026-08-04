"""Red canary for interpreter-startup isolation of admission invocations.

`.github/workflows/candidate-admission.yml` runs the admission validator twice.
Without `-S`, the `site` module executes any `sitecustomize.py`, `usercustomize.py`,
or `.pth` file reachable from `sys.path` at interpreter startup, before the
validator module and before `tools/__init__.py`. `-S` disables `site` entirely, so
the control generalizes to startup hooks nobody has enumerated rather than naming
two paths.

Both halves are required. A test that only shows "the hook did not run" cannot
distinguish real isolation from a hook that never would have run. The
`PYTHONPATH`-reachable hook below runs under the non-isolated invocation and does
not run under the isolated one, on the same interpreter, in the same directory,
with the same environment.

Every runtime test reads its flags from the workflow rather than hardcoding `-S`,
so deleting the flag from the shipped command reds this file instead of leaving a
canary that proves only what it was handed.

Not every startup-affecting flag is a safe substitute. Measured 2026-08-03 on
CPython 3.14.6, against the same `PYTHONPATH` hook and the real validator:

    (none)      exit=0  marker=PRESENT
    -S          exit=0  marker=ABSENT
    -I          exit=1  marker=ABSENT    ModuleNotFoundError: tools
    -P          exit=1  marker=PRESENT   ModuleNotFoundError: tools

`-I` and `-P` drop the script directory from `sys.path`, which breaks
`python3 -m tools.*` outright; `-P` does not even block the hook. A regex that
accepted them would stay green while bricking admission for every candidate, so
`test_shipped_flags_do_not_break_the_validator` executes whatever the workflow
actually ships instead of trusting the pattern.

A hook written at the *repository root* is not imported by `site` under either
invocation form, because CPython inserts the `-m` invocation root into `sys.path`
after `site` has already run. That premise correction is recorded here as prose
because it is not a property of this change: an assertion about it would be
trivially true with and without `-S` and would prove nothing about isolation.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/candidate-admission.yml"

INVOCATION = re.compile(r"python3((?: -[A-Za-z]+)*) -m tools\.admission_root_v1")
REQUIRED_FLAG = "-S"

HOOK_SOURCE = (
    "import os\n"
    "marker = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'marker')\n"
    "with open(marker, 'w', encoding='utf-8') as handle:\n"
    "    handle.write('startup hook executed')\n"
)


def shipped_flag_sets() -> list[list[str]]:
    """Return the interpreter flags of every admission invocation in the workflow."""

    workflow = WORKFLOW.read_text(encoding="utf-8")
    return [match.split() for match in INVOCATION.findall(workflow)]


def write_hook(directory: Path) -> Path:
    """Write a `sitecustomize.py` that records the fact that it ran."""

    (directory / "sitecustomize.py").write_text(HOOK_SOURCE, encoding="utf-8")
    return directory / "marker"


def run_validator(flags: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the admission self-check exactly as the workflow does."""

    return subprocess.run(
        [sys.executable, *flags, "-m", "tools.admission_root_v1", "--self-check", "--root", "."],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class AdmissionStartupIsolationTests(unittest.TestCase):
    """Prove the admission interpreter refuses untrusted startup hooks."""

    def base_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONSTARTUP", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def isolation_flags(self) -> list[str]:
        """The flag set the workflow ships, asserted to be uniform across invocations."""

        flag_sets = shipped_flag_sets()
        self.assertTrue(flag_sets, "no admission invocation found in the workflow")
        self.assertEqual(
            [sorted(flags) for flags in flag_sets],
            [sorted(flag_sets[0])] * len(flag_sets),
            "admission invocations disagree about interpreter flags",
        )
        return flag_sets[0]

    def test_reachable_startup_hook_runs_without_isolation(self) -> None:
        """Red half: without isolation flags the hook executes inside the process.

        This is the non-isolated control, so it carries no flags by construction.
        It reds if the fixture hook ever stops being reachable, which is what makes
        the isolated half below mean anything.
        """

        with tempfile.TemporaryDirectory() as tmp:
            marker = write_hook(Path(tmp))
            env = self.base_env()
            env["PYTHONPATH"] = tmp

            result = run_validator([], env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                marker.exists(),
                "the fixture hook never ran, so the isolated half proves nothing",
            )

    def test_reachable_startup_hook_is_blocked_by_shipped_flags(self) -> None:
        """Green half: the same hook cannot execute under the shipped invocation."""

        with tempfile.TemporaryDirectory() as tmp:
            marker = write_hook(Path(tmp))
            env = self.base_env()
            env["PYTHONPATH"] = tmp

            result = run_validator(self.isolation_flags(), env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(
                marker.exists(),
                "a startup hook executed inside an isolated admission interpreter",
            )

    def test_shipped_flags_do_not_break_the_validator(self) -> None:
        """The shipped flags must actually run: `-I` and `-P` do not.

        Isolation that exits 1 with `No module named tools` is not isolation, it is
        an outage. This runs the exact flag set from the workflow rather than a
        hardcoded `-S`, so swapping in a plausible-looking harder flag reds here.
        """

        flags = self.isolation_flags()

        self.assertIn(
            REQUIRED_FLAG,
            flags,
            "the workflow no longer disables `site` for admission invocations",
        )

        result = run_validator(flags, self.base_env())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")

    def test_workflow_isolates_both_admission_invocations(self) -> None:
        """Every admission invocation in the workflow carries the isolation flag."""

        flag_sets = shipped_flag_sets()

        self.assertEqual(len(flag_sets), 2, flag_sets)
        for flags in flag_sets:
            self.assertIn(REQUIRED_FLAG, flags, flag_sets)


if __name__ == "__main__":
    unittest.main()
