"""Pin that `validate_decision_context` gates structure, not content quality.

These tests claim no control. They characterize one standing property of one
function: it accepts a semantically hollow material decision as readily as a
well-formed one, because it cannot read meaning. Nothing here argues that is
a defect. The file exists so a later reader cannot mistake a clean validator
pass for evidence that a decision was thought through, and so a change that
does add a content check has an honest before-picture to red against.

Scope note: `docs/experiments/grill-elicitation.md` also reports that the
same hollowness survives `verify_outcome_receipt` to a `supported` verdict.
That half was established by READING the receipt contract, not by executing a
bound receipt, and nothing in this module exercises it. An earlier docstring
claimed both functions were characterized here; only this one is.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from aec.mentoring import validate_decision_context


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "decision-context"
REVISION = "0" * 39 + "a"


def load(name: str) -> dict:
    """Load one decision-context fixture bound to a fixed test revision."""
    text = (FIXTURES / f"{name}.json").read_text(encoding="utf-8")
    return json.loads(text.replace("__REVISION__", REVISION))


class ElicitationQualityIsUncontracted(unittest.TestCase):
    """Structure is contracted. Whether anyone thought is not."""

    def test_grilled_decision_validates(self) -> None:
        """The interrogated fixture is a valid material decision."""
        self.assertEqual([], validate_decision_context(load("grilled"), revision=REVISION))

    def test_hollow_decision_validates_identically(self) -> None:
        """Every field restates its own name, and the contract still passes.

        This is the pinned fact. `hollow.json` names no real tradeoff, its
        falsifier restates the recommendation, and its measure ("goodness",
        in "points") could never be observed. It is accepted.
        """
        self.assertEqual([], validate_decision_context(load("hollow"), revision=REVISION))

    def test_contradiction_between_declared_facts_is_rejected(self) -> None:
        """The two semantic rules that do exist compare declared facts only.

        Confidence may not exceed the evidence supporting it, and a target
        must move the way its direction claims. Both are checkable because
        both compare two values already inside the contract -- which is
        exactly why no rule can reach the prose.
        """
        payload = load("hollow")
        # Broken from BELOW: hollow.json already declares high/direct-verified,
        # and direct-verified is the only quality supporting high, so there is
        # nothing to raise confidence above.
        payload["context"]["evidence_quality"] = "assumed"
        payload["recommendation"]["expected_result"]["direction"] = "decrease"

        errors = validate_decision_context(payload, revision=REVISION)

        # Pinned exactly: the experiment record publishes this count, so a third
        # error appearing must red here rather than leave the record silently wrong.
        self.assertEqual(2, len(errors), errors)
        self.assertIn(
            "decision_context.recommendation.confidence exceeds the declared evidence quality",
            errors,
        )
        self.assertIn(
            "decision_context.recommendation.expected_result.target contradicts "
            "decision_context.recommendation.expected_result.direction",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
