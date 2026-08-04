"""The read-only boundary is AEC's central safety claim. Nothing red-tested it.

`AGENTS.md` opens with it:

    AEC is read-only mentoring logic. It must never execute a recommended
    procedure or mutate lifecycle, project, review, merge, or deployment state.

`aec/contracts.py` enforces it in two lines: `lifecycle_authority` must equal
`consumer-owned`, and `aec_mode` must equal `read-only-mentor`. Both are exact
equality against a single permitted value, which is the correct shape -- a set
that can be widened is a boundary that can be negotiated.

Measured 2026-08-03: widening BOTH checks to also accept `aec-owned` and
`executor`, then regenerating the source declaration so no digest drift masked
the result, left the entire suite green. Exit 0. AEC could declare itself the
lifecycle authority and an executor over a consumer's repository, and every
gate in this repository would have passed it.

The existing tests were not wrong, they were the wrong shape: every one of them
supplies the valid value and asserts a happy path. `test_foundation_validation`
and `test_aec_prompt_hook` between them mention `consumer-owned` and
`read-only-mentor` eight times, and not one of those is a rejection.

That is the difference between a value being *used* everywhere and a value
being *required*. Only a rejected case proves the requirement.
"""

from __future__ import annotations

import unittest

from aec.contracts import validate_project_profile


def profile(**overrides: object) -> dict[str, object]:
    """A profile that is valid except for what the caller deliberately breaks."""
    base: dict[str, object] = {
        "aec_mode": "read-only-mentor",
        "agent_adapters": ["claude-code", "codex"],
        "lifecycle_authority": "consumer-owned",
        "profile_version": "canary:1.0.0",
        "project": "owner/repository",
        "schema_version": "1.0.0",
        "workflow": "ticket-to-pr",
    }
    base.update(overrides)
    return base


class ReadOnlyAuthorityBoundaryTests(unittest.TestCase):
    def test_the_baseline_profile_is_accepted(self) -> None:
        """Without this, every rejection below could pass for the wrong reason."""
        self.assertEqual([], validate_project_profile(profile()))

    def test_aec_may_not_be_declared_the_lifecycle_authority(self) -> None:
        """RED CANARY: the value that would make AEC the writer of consumer state."""
        for claimed in ("aec-owned", "aec", "shared", "framework-owned", ""):
            with self.subTest(lifecycle_authority=claimed):
                errors = validate_project_profile(
                    profile(lifecycle_authority=claimed)
                )
                self.assertIn(
                    "consumer must own lifecycle authority",
                    errors,
                    f"{claimed!r} was accepted as a lifecycle authority; the "
                    "consumer is the only permitted owner",
                )

    def test_aec_may_not_be_declared_anything_but_a_read_only_mentor(self) -> None:
        """RED CANARY: the value that would let AEC claim execution authority."""
        for claimed in ("executor", "read-write-mentor", "agent", "mentor", ""):
            with self.subTest(aec_mode=claimed):
                errors = validate_project_profile(profile(aec_mode=claimed))
                self.assertIn(
                    "AEC consumer mode must be read-only-mentor",
                    errors,
                    f"{claimed!r} was accepted as an AEC mode; read-only-mentor "
                    "is the only permitted value",
                )

    def test_both_boundaries_reject_independently(self) -> None:
        """Neither check may come to rely on the other also failing.

        If one were ever relaxed, a profile breaking only that one must still
        be rejected. Asserting them together would hide exactly that.
        """
        authority_only = validate_project_profile(
            profile(lifecycle_authority="aec-owned")
        )
        mode_only = validate_project_profile(profile(aec_mode="executor"))

        self.assertNotIn("AEC consumer mode must be read-only-mentor", authority_only)
        self.assertNotIn("consumer must own lifecycle authority", mode_only)
        self.assertTrue(authority_only)
        self.assertTrue(mode_only)


if __name__ == "__main__":
    unittest.main()
