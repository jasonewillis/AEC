"""Base-admitted two-seed, two-run resolver behavior proof."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from aec.resolver import ResolutionDecision, resolve
from tools.prove_foundation_behavior import (
    EXPECTED_AGGREGATE,
    decision_aggregate,
    prove_behavior,
)


ROOT = Path(__file__).resolve().parents[1]


class FoundationBehaviorTests(unittest.TestCase):
    """Prove exact resolver behavior after base-owned admission."""

    def test_ten_decisions_match_frozen_aggregate(self) -> None:
        self.assertEqual(EXPECTED_AGGREGATE, decision_aggregate(ROOT))

    def test_two_hash_seeds_and_two_runs_are_byte_identical(self) -> None:
        outputs = []
        for seed in ("1", "2"):
            for _ in range(2):
                environment = dict(os.environ, PYTHONHASHSEED=seed)
                result = subprocess.run(
                    [sys.executable, "-m", "tools.prove_foundation_behavior"],
                    cwd=ROOT,
                    env=environment,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                outputs.append(result.stdout)

        self.assertEqual(
            [EXPECTED_AGGREGATE + "\n"] * 4,
            outputs,
        )

    def test_divergent_behavior_fails_with_expected_literal_unchanged(self) -> None:
        def divergent(request: object, catalog: object) -> object:
            decision = resolve(request, catalog)
            if not isinstance(decision, ResolutionDecision):
                return decision
            return ResolutionDecision(
                canonical_bytes=decision.canonical_bytes + b" ",
                hashed_bytes=decision.hashed_bytes,
                resolution_hash=decision.resolution_hash,
            )

        with self.assertRaisesRegex(ValueError, "behavior aggregate mismatch"):
            prove_behavior(ROOT, divergent)


if __name__ == "__main__":
    unittest.main()
