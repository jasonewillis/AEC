"""An observation must be actionable before AEC will carry it.

Agents notice things and surface them as prose that evaporates into the
transcript. The real example that prompted #131:

    "this check-in asked me to verify conditions that were already settled,
    because a scheduled message can't know the world moved. Same shape as the
    stale codex-review-blocking label on #9760 and the a02b0721 failure notices
    -- recorded state outliving the thing it described."

Three real instances and a transferable principle, and still unactionable: it
says nothing about what to do, who decides, or what would show the pattern is
not real.

AEC does not supply the missing parts. `coaching-interaction.md` is explicit
that it "does not select, score, or rank" -- it checks completeness and
republishes bound to the card hash. So the contract refuses an observation that
is not yet actionable, and the refusal names what is missing. The forcing
function is the value; authorship stays with the agent.

These tests pin the contract. Wiring it into the request, card and renderer is
phase 2 and is deliberately not asserted here.
"""

from __future__ import annotations

import copy
import unittest

from aec.mentoring import (
    MINIMUM_OBSERVATION_INSTANCES,
    OBSERVATION_CONTEXT_SCHEMA_VERSION,
    validate_observation_context,
)


REVISION = "a" * 40

# The #131 example, completed to what the contract requires. The three fields
# it originally lacked are `action`, `authority` and `refuted_if`.
OBSERVATION = {
    "action": (
        "Re-derive any status artifact on read rather than citing it, starting "
        "with the codex-review-blocking label."
    ),
    "authority": {
        "owner": "consumer-owner",
        "reason": "Changing how status artifacts are consumed is the owner's call.",
    },
    "confidence": "medium",
    "context": {"evidence_quality": "indirect", "revision": REVISION},
    "instances": [
        "codex-review-blocking label on #9760",
        "a02b0721 failure notices",
        "a scheduled check-in asking to verify settled conditions",
    ],
    "recognition_heuristic": (
        "A status artifact is cited as current without anything re-checking it."
    ),
    "refuted_if": (
        "Each artifact is re-derived at read time, so none can outlive its subject."
    ),
    "schema_version": OBSERVATION_CONTEXT_SCHEMA_VERSION,
    "statement": "Recorded state outlives the thing it described.",
}


def without(field: str) -> dict:
    record = copy.deepcopy(OBSERVATION)
    del record[field]
    return record


def replacing(**overrides: object) -> dict:
    record = copy.deepcopy(OBSERVATION)
    record.update(overrides)
    return record


class ObservationContractTests(unittest.TestCase):
    def test_a_complete_observation_is_accepted(self) -> None:
        """Without this, every rejection below could pass for the wrong reason."""
        self.assertEqual(
            [], validate_observation_context(OBSERVATION, revision=REVISION)
        )

    def test_absence_is_valid_because_most_turns_notice_nothing(self) -> None:
        """Null is the correct shape for a turn with nothing to report.

        The alternative -- requiring every turn to produce an observation --
        would guarantee manufactured ones, which is the failure mode the
        two-instance floor exists to prevent.
        """
        self.assertEqual([], validate_observation_context(None))

    def test_one_instance_is_a_hunch_not_a_pattern(self) -> None:
        """RED CANARY: the floor that stops this becoming a noise channel."""
        single = replacing(instances=["codex-review-blocking label on #9760"])

        errors = validate_observation_context(single, revision=REVISION)

        self.assertTrue(errors)
        self.assertIn("at least", errors[0])
        self.assertIn("hunch", errors[0])

    def test_repeating_one_identity_does_not_reach_the_floor(self) -> None:
        """Two entries naming the same occurrence is one observation, twice."""
        duplicated = replacing(
            instances=["#9760 stale label", "#9760 stale label"]
        )

        errors = validate_observation_context(duplicated, revision=REVISION)

        self.assertTrue(any("distinct" in error for error in errors), errors)

    def test_every_required_narrative_field_is_refused_when_absent(self) -> None:
        """Each of these is a question a reader would otherwise be left with."""
        for field in ("statement", "recognition_heuristic", "refuted_if"):
            with self.subTest(field=field):
                errors = validate_observation_context(
                    without(field), revision=REVISION
                )
                self.assertTrue(errors, f"{field} may not be optional")

    def test_a_blank_field_does_not_satisfy_the_contract(self) -> None:
        errors = validate_observation_context(
            replacing(refuted_if="   "), revision=REVISION
        )
        self.assertTrue(any("refuted_if" in error for error in errors), errors)

    def test_action_may_be_null_but_must_be_stated(self) -> None:
        """Watch-only is legitimate; silently omitting the field is not.

        Forcing a next step where there is not one yet would produce fabricated
        actions, which is worse than an honest null. But the author has to say
        so, so a reader can tell 'nothing to do yet' from 'nobody considered it'.
        """
        self.assertEqual(
            [], validate_observation_context(replacing(action=None), revision=REVISION)
        )
        self.assertTrue(validate_observation_context(without("action"), revision=REVISION))

    def test_confidence_may_not_exceed_the_evidence_behind_it(self) -> None:
        """RED CANARY: the same rule recommendations already live under."""
        overclaimed = replacing(
            confidence="high", context={"evidence_quality": "assumed", "revision": REVISION}
        )

        errors = validate_observation_context(overclaimed, revision=REVISION)

        self.assertTrue(any("exceeds" in error for error in errors), errors)

    def test_an_observation_bound_to_another_revision_is_refused(self) -> None:
        errors = validate_observation_context(OBSERVATION, revision="b" * 40)
        self.assertTrue(errors)

    def test_an_unknown_field_is_refused_rather_than_ignored(self) -> None:
        """Closed field set: free text cannot ride along in an extra key."""
        smuggled = replacing(notes="an unstructured aside")
        self.assertTrue(validate_observation_context(smuggled, revision=REVISION))

    def test_the_floor_is_two(self) -> None:
        """Pins the constant, so lowering it to one is a visible edit."""
        self.assertEqual(2, MINIMUM_OBSERVATION_INSTANCES)


if __name__ == "__main__":
    unittest.main()
