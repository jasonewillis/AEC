"""`--check` must name the drifted path, and must still refuse to write it.

`artifacts` and `proof_closure` carry human-assigned metadata, so
`generate_source_declaration.py` deliberately does not regenerate them. That
manual step is the control: a candidate declares digests for files it must not
be able to change silently, and auto-rewriting them would make tampering and a
legitimate edit indistinguishable at the tool level.

Not regenerating them is not the same as not reporting them. Before this,
editing a declared file surfaced later and elsewhere as

    AssertionError: Tuples differ: () != ('artifacts',)

from `self_check` -- the section, never the path. Four times across
2026-08-03/04 that cost a diagnosis detour, and once it did real damage: an
invariant-sweep mutation left a stale artifact digest, `setUpClass` errored, the
error was read as noise rather than as the run being invalid, and a guarded
invariant was reported as UNGUARDED. A false finding nearly became a pull
request.

These tests pin both halves of the fix, because either alone would be wrong:
the drift must be *named*, and it must still not be *written*.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECLARATION = ROOT / ".github" / "admission" / "v1" / "source-declaration.json"

# One file from each hand-maintained section, chosen because both are ordinary
# regular files -- symlinks and directories are the owning section's business.
ARTIFACT_TARGET = ROOT / "schemas" / "consumer-state.schema.json"
PROOF_CLOSURE_TARGET = ROOT / "tools" / "validate_foundation.py"


def check() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/generate_source_declaration.py", "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


class DigestDriftNamesThePathTests(unittest.TestCase):
    """Each test perturbs one real declared file and restores it in tearDown."""

    target: Path | None = None
    original: bytes | None = None

    def tearDown(self) -> None:
        if self.target is not None and self.original is not None:
            self.target.write_bytes(self.original)
        self.target = None
        self.original = None

    def drift(self, target: Path) -> subprocess.CompletedProcess[str]:
        # Precondition: a clean tree must pass, or a failure below proves
        # nothing about the perturbation that follows it.
        before = check()
        self.assertEqual(
            0,
            before.returncode,
            "the tree already fails --check, so this canary cannot isolate the "
            f"condition it claims to test:\n{before.stdout}{before.stderr}",
        )
        self.target = target
        self.original = target.read_bytes()
        # A trailing newline changes the bytes without changing the meaning,
        # so the file stays valid and only its digest moves.
        target.write_bytes(self.original + b"\n")
        return check()

    def test_a_drifted_artifact_is_named_with_both_digests(self) -> None:
        result = self.drift(ARTIFACT_TARGET)
        output = result.stdout + result.stderr

        self.assertNotEqual(0, result.returncode)
        self.assertIn("artifacts.schemas/consumer-state.schema.json", output)
        self.assertIn("declared", output)
        self.assertIn("actual", output)

    def test_a_drifted_proof_closure_path_is_named(self) -> None:
        result = self.drift(PROOF_CLOSURE_TARGET)
        output = result.stdout + result.stderr

        self.assertNotEqual(0, result.returncode)
        self.assertIn("proof_closure.tools/validate_foundation.py", output)

    def test_the_generator_still_refuses_to_write_those_sections(self) -> None:
        """RED CANARY for the control itself, not the diagnosis.

        If a future change made the generator "helpfully" regenerate these,
        the drift above would vanish silently and the manual review step with
        it. Running the generator over a drifted tree must leave the declared
        digest exactly as committed.
        """
        self.target = ARTIFACT_TARGET
        self.original = ARTIFACT_TARGET.read_bytes()
        declared_before = json.loads(DECLARATION.read_text(encoding="utf-8"))[
            "artifacts"
        ]["schemas/consumer-state.schema.json"][1]

        ARTIFACT_TARGET.write_bytes(self.original + b"\n")
        subprocess.run(
            [sys.executable, "tools/generate_source_declaration.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )

        declared_after = json.loads(DECLARATION.read_text(encoding="utf-8"))[
            "artifacts"
        ]["schemas/consumer-state.schema.json"][1]
        self.assertEqual(
            declared_before,
            declared_after,
            "the generator rewrote a hand-maintained artifact digest; that "
            "removes the manual step which is the actual control",
        )


if __name__ == "__main__":
    unittest.main()
