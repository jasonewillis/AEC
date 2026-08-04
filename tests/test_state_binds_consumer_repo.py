"""`state` must be able to describe a repository other than AEC's own.

`checkpoint` gained `--project-root` in #109 so a consumer state could be
*checked* against the consumer's HEAD. `state` never gained the matching flag,
so the only way to *build* such a state was to copy
`docs/consumer-kit/state_producer_template.py` and call `build_state` directly.

The gap was not theoretical. The prompt hook at `~/.claude/hooks/aec-coach.py`
shells out to `state` with `cwd=AEC_ROOT` and no way to say otherwise, so the
card it rendered in *every* repository reported AEC's revision and the project
`jasonewillis/AEC`. Observed 2026-08-03 in an unrelated repository: the
`REVISION` line showed AEC's `main` HEAD while the phase was inferred from the
other repository's branch and pull request. The one line on the card claiming
exactness named the wrong repository.

`--project-root` and `--profile` travel together deliberately. A state carrying
another repository's revision under AEC's profile, or AEC's revision under
another project's name, describes a repository that does not exist. These tests
pin both halves, and pin that omitting them leaves today's behaviour unchanged.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CONSUMER_PROFILE = {
    "aec_mode": "read-only-mentor",
    "agent_adapters": ["claude-code"],
    "lifecycle_authority": "consumer-owned",
    "profile_version": "consumer-canary:1.0.0",
    "project": "someone-else/their-repository",
    "schema_version": "1.0.0",
    "workflow": "ticket-to-pr",
}


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def build_consumer_repo(directory: Path) -> tuple[Path, str]:
    """Create a throwaway repository with exactly one commit, and return its HEAD."""
    repo = directory / "consumer"
    repo.mkdir()
    git("init", "-q", cwd=repo)
    git("config", "user.email", "canary@example.invalid", cwd=repo)
    git("config", "user.name", "canary", cwd=repo)
    (repo / "README.md").write_text("consumer\n", encoding="utf-8")
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "initial", cwd=repo)
    return repo, git("rev-parse", "HEAD", cwd=repo)


def run_state(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.aec_coach", "state", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


class StateBindsTheNamedRepositoryTests(unittest.TestCase):
    def test_project_root_binds_the_consumer_head_not_aec(self) -> None:
        """RED CANARY: the defect that put AEC's SHA on every consumer's card."""
        aec_head = git("rev-parse", "HEAD", cwd=ROOT)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            repo, consumer_head = build_consumer_repo(work)
            self.assertNotEqual(
                aec_head, consumer_head, "the canary needs two distinct HEADs"
            )
            profile_path = work / "profile.json"
            profile_path.write_text(json.dumps(CONSUMER_PROFILE), encoding="utf-8")
            out = work / "state.json"

            result = run_state(
                "--task", "canary", "--phase", "Review", "--lane", "INFRA",
                "--project-root", str(repo),
                "--profile", str(profile_path),
                "--out", str(out),
            )
            self.assertEqual(0, result.returncode, result.stderr)

            state = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(consumer_head, state["revision"]["identity"])
            self.assertNotEqual(aec_head, state["revision"]["identity"])
            self.assertEqual(
                "someone-else/their-repository",
                state["consumer_profile"]["project"],
            )

    def test_omitting_both_flags_still_describes_aec(self) -> None:
        """Backward compatibility: every existing caller passes neither flag."""
        aec_head = git("rev-parse", "HEAD", cwd=ROOT)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "state.json"
            result = run_state(
                "--task", "canary", "--phase", "Intake", "--lane", "INFRA",
                "--out", str(out),
            )
            self.assertEqual(0, result.returncode, result.stderr)

            state = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(aec_head, state["revision"]["identity"])
            self.assertEqual("jasonewillis/AEC", state["consumer_profile"]["project"])

    def test_a_profile_that_claims_authority_is_refused(self) -> None:
        """A caller-supplied profile must not become a way around the read-only rule."""
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            repo, _ = build_consumer_repo(work)
            hostile = dict(CONSUMER_PROFILE, lifecycle_authority="aec-owned")
            profile_path = work / "hostile.json"
            profile_path.write_text(json.dumps(hostile), encoding="utf-8")
            out = work / "state.json"

            result = run_state(
                "--task", "canary", "--phase", "Review", "--lane", "INFRA",
                "--project-root", str(repo),
                "--profile", str(profile_path),
                "--out", str(out),
            )

            self.assertNotEqual(0, result.returncode)
            self.assertFalse(out.exists(), "a refused state must not be written")

    def test_a_malformed_profile_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            profile_path = work / "broken.json"
            profile_path.write_text("{not json", encoding="utf-8")
            out = work / "state.json"

            result = run_state(
                "--task", "canary", "--phase", "Intake", "--lane", "INFRA",
                "--profile", str(profile_path),
                "--out", str(out),
            )

            self.assertNotEqual(0, result.returncode)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
