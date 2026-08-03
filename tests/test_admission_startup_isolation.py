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

Measured 2026-08-03 on CPython 3.12.1, 3.12.13, and 3.14.6: a hook written at the
*repository root* is not imported by `site` under either invocation form, because
CPython inserts the `-m` invocation root into `sys.path` after `site` has already
run. That is why the repository-root case asserts only the isolated half and the
`PYTHONPATH` case carries the both-halves proof.
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

ISOLATED_INVOCATION = re.compile(r"python3 (?:-I|-P|-S)[^\n]*-m tools\.admission_root_v1")
ANY_INVOCATION = re.compile(r"python3 [^\n]*-m tools\.admission_root_v1")

HOOK_SOURCE = (
    "import os\n"
    "marker = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'marker')\n"
    "with open(marker, 'w', encoding='utf-8') as handle:\n"
    "    handle.write('startup hook executed')\n"
)


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

    def test_reachable_startup_hook_runs_without_isolation(self) -> None:
        """Red half: without `-S` the hook executes inside the admission process."""

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

    def test_reachable_startup_hook_is_blocked_by_isolation(self) -> None:
        """Green half: the same hook cannot execute under the shipped `-S` form."""

        with tempfile.TemporaryDirectory() as tmp:
            marker = write_hook(Path(tmp))
            env = self.base_env()
            env["PYTHONPATH"] = tmp

            result = run_validator(["-S"], env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(
                marker.exists(),
                "a startup hook executed inside an isolated admission interpreter",
            )

    def test_isolation_does_not_break_validator_imports(self) -> None:
        """`-S` removes site-packages; the validator is standard library only."""

        result = run_validator(["-S"], self.base_env())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")

    def test_repository_root_hook_never_executes_under_isolation(self) -> None:
        """A repository-root `sitecustomize.py` cannot reach the isolated process."""

        marker = ROOT / "marker"
        hook = ROOT / "sitecustomize.py"
        self.assertFalse(hook.exists(), "repository already carries a startup hook")
        self.assertFalse(marker.exists(), "unexpected marker file in the repository")
        try:
            write_hook(ROOT)
            result = run_validator(["-S"], self.base_env())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(
                marker.exists(),
                "a repository-root startup hook executed during admission",
            )
        finally:
            hook.unlink(missing_ok=True)
            marker.unlink(missing_ok=True)

    def test_workflow_isolates_both_admission_invocations(self) -> None:
        """Every admission invocation in the workflow carries an isolation flag."""

        workflow = WORKFLOW.read_text(encoding="utf-8")
        isolated = ISOLATED_INVOCATION.findall(workflow)
        every = ANY_INVOCATION.findall(workflow)

        self.assertEqual(len(isolated), 2, workflow)
        self.assertEqual(len(every), 2, workflow)
        self.assertEqual(sorted(isolated), sorted(every))


if __name__ == "__main__":
    unittest.main()
