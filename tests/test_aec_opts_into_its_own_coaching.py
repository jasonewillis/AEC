"""AEC must opt into its own coaching the same way every consumer does.

The prompt hook (`~/.claude/hooks/aec-coach.py`) renders a card only for a
repository carrying `.claude/aec-profile.json`. Before that gate existed it
rendered in EVERY git repository using AEC's own identity: a card in an
unrelated project reported `jasonewillis/AEC` and AEC's HEAD while the phase
was inferred from the other project's branch.

The gate initially special-cased AEC's own checkout as always-opted-in. That
was convenient and wrong for the same reason everything else found this week
was wrong: it meant AEC never travelled the path it asks consumers to travel,
so a break in that path would show up first for a consumer rather than here.

This file pins the committed profile instead. It is deliberately not a
happy-path assertion that the file parses -- it asserts the file satisfies the
same validator that would reject a consumer's profile, and that it agrees with
the in-code default it replaces, so the two cannot drift apart silently.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from aec.contracts import validate_project_profile
from aec.state_builder import AEC_SELF_PROFILE


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / ".claude" / "aec-profile.json"


class AecOptsIntoItsOwnCoachingTests(unittest.TestCase):
    def test_the_opt_in_profile_is_committed(self) -> None:
        self.assertTrue(
            PROFILE_PATH.is_file(),
            "AEC has no .claude/aec-profile.json, so the prompt hook will not "
            "coach this repository unless it special-cases it",
        )

    def test_the_profile_satisfies_the_consumer_contract(self) -> None:
        """The same validator that would refuse a consumer's profile."""
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        self.assertEqual([], validate_project_profile(profile))

    def test_the_committed_profile_agrees_with_the_in_code_default(self) -> None:
        """Two sources of the same fact must not drift.

        `AEC_SELF_PROFILE` is what `build_state` uses when no profile is
        supplied; the committed file is what the hook passes explicitly. If
        they disagreed, AEC's card would describe a different project
        depending on which path produced it.
        """
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(AEC_SELF_PROFILE, profile)

    def test_the_profile_cannot_claim_authority(self) -> None:
        """RED CANARY: the committed file is a real input to state construction."""
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        self.assertEqual("consumer-owned", profile["lifecycle_authority"])
        self.assertEqual("read-only-mentor", profile["aec_mode"])


if __name__ == "__main__":
    unittest.main()
