"""Evidence-conditional mentoring: what it fixes, and what it provably cannot.

Issue #92 observed the same five-line teaching block rendering ~30 consecutive
times in one session. The catalog held exactly one `mentoring` record per phase,
so once a task was pinned to a phase, every turn produced identical copy.

These tests pin the half of that defect AEC can own. The other half is stated
here too, as an executable claim rather than a comment: a pure resolver cannot
vary its output across turns whose *input* did not change, so suppressing an
unchanged repeat belongs to the consumer's prompt hook, which legitimately holds
session state. `test_identical_requests_stay_byte_identical` is the test that
would fail if someone ever "fixed" repetition by making the resolver remember.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from aec.resolver import (
    ResolutionRejection,
    _evidence_level,
    _selected_mentoring,
    resolve,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads(
    (ROOT / "config/procedures/ticket-to-pr.json").read_text(encoding="utf-8")
)
GOLDEN = ROOT / "tests/fixtures/resolver/golden"


def procedure_for(phase: str) -> dict:
    return next(item for item in CATALOG["procedures"] if item["phase"] == phase)


class EvidenceLevelTests(unittest.TestCase):
    def test_levels_partition_on_how_much_required_evidence_is_accepted(self) -> None:
        required = ["red-case-result", "green-case-result"]
        cases = (
            (set(), "unmet"),
            ({"red-case-result"}, "partial"),
            ({"green-case-result"}, "partial"),
            (set(required), "met"),
            # Evidence for something this procedure never asked for is not
            # progress toward its gate.
            ({"unrelated-report"}, "unmet"),
        )
        for accepted, expected in cases:
            with self.subTest(accepted=sorted(accepted)):
                self.assertEqual(expected, _evidence_level(required, accepted))

    def test_a_procedure_requiring_nothing_is_met_not_unmet(self) -> None:
        """Fail-open here would be wrong; a gate with no proof to collect is open."""
        self.assertEqual("met", _evidence_level([], set()))


class VariantSelectionTests(unittest.TestCase):
    def test_authored_phases_teach_a_different_lesson_at_each_level(self) -> None:
        for phase in ("Build", "Verify"):
            with self.subTest(phase=phase):
                procedure = procedure_for(phase)
                lessons = {
                    _selected_mentoring(procedure, level)["lesson"]
                    for level in ("unmet", "partial", "met")
                }
                self.assertEqual(
                    3,
                    len(lessons),
                    f"{phase} renders {len(lessons)} distinct lesson(s) across three "
                    "evidence levels; issue #92 is the case where that number is 1",
                )

    def test_an_unauthored_phase_falls_back_rather_than_rendering_empty(self) -> None:
        procedure = procedure_for("Intake")
        self.assertEqual({}, procedure["mentoring_variants"])
        for level in ("unmet", "partial", "met"):
            with self.subTest(level=level):
                self.assertEqual(
                    procedure["mentoring"], _selected_mentoring(procedure, level)
                )

    def test_every_variant_carries_the_full_teaching_contract(self) -> None:
        """A variant missing a field would teach a lesson without its gate reason."""
        required = {"lesson", "recognition_heuristic", "why_gate_exists"}
        for procedure in CATALOG["procedures"]:
            for level, block in procedure["mentoring_variants"].items():
                with self.subTest(phase=procedure["phase"], level=level):
                    self.assertEqual(required, set(block))
                    for name, value in block.items():
                        self.assertTrue(value.strip(), f"{name} is blank")


class ResolvedCardTests(unittest.TestCase):
    """The selection has to survive the resolver, not just the helper."""

    def build_request(self, accepted: list[str]) -> dict:
        request = json.loads((GOLDEN / "build.json").read_text(encoding="utf-8"))
        request["evidence"] = [
            {
                "accepted": True,
                "environment": request["environment"],
                "kind": kind,
                "revision": request["revision"],
            }
            for kind in accepted
        ]
        return request

    def lesson_for(self, accepted: list[str]) -> str:
        decision = resolve(self.build_request(accepted), CATALOG)
        self.assertNotIsInstance(decision, ResolutionRejection)
        return decision.to_dict()["mentoring"]["lesson"]

    def test_a_real_card_changes_its_lesson_as_evidence_accumulates(self) -> None:
        unmet = self.lesson_for([])
        partial = self.lesson_for(["red-case-result"])
        met = self.lesson_for(["red-case-result", "green-case-result"])

        self.assertEqual(3, len({unmet, partial, met}))
        # Before this change every one of these was the same string.
        self.assertNotEqual(unmet, partial)
        self.assertNotEqual(partial, met)

    def test_identical_requests_stay_byte_identical(self) -> None:
        """The boundary claim: AEC may not vary output for an unchanged request.

        This is the test that reds if repetition is ever "solved" by giving the
        resolver session memory. Suppressing an unchanged repeat is the
        consumer hook's job precisely because doing it here would break the
        determinism every card hash depends on.
        """
        request = self.build_request(["red-case-result"])
        first = resolve(copy.deepcopy(request), CATALOG)
        second = resolve(copy.deepcopy(request), CATALOG)
        self.assertNotIsInstance(first, ResolutionRejection)
        self.assertNotIsInstance(second, ResolutionRejection)
        self.assertEqual(first.canonical_bytes, second.canonical_bytes)
        self.assertEqual(first.resolution_hash, second.resolution_hash)


class BlockedCardTests(unittest.TestCase):
    def test_a_blocked_card_keeps_the_canonical_block(self) -> None:
        """A blocked reader is not standing at the evidence gate being taught."""
        request = json.loads((GOLDEN / "build.json").read_text(encoding="utf-8"))
        request["evidence"] = [
            {
                "accepted": True,
                "environment": request["environment"],
                "kind": "red-case-result",
                "revision": request["revision"],
            }
        ]
        request["blockers"] = [
            {
                "active": True,
                "identity": "blocker-policy-conflict",
                "reason_code": "POLICY_CONFLICT",
            }
        ]
        decision = resolve(request, CATALOG)
        self.assertNotIsInstance(decision, ResolutionRejection)
        payload = decision.to_dict()
        self.assertEqual("Blocked", payload["gate"])
        self.assertEqual(
            procedure_for("Build")["mentoring"],
            payload["mentoring"],
            "a blocked card must not teach the partial-evidence lesson",
        )


if __name__ == "__main__":
    unittest.main()
