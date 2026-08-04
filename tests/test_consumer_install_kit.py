"""Executable proof for the consumer install kit (AEC issue #109).

`docs/consumer-kit/register-hook.md` and
`docs/consumer-kit/state_producer_template.py` are the whole onboarding
surface: a consumer copies them, runs them, and either reaches a card or does
not. Until this file existed neither was executed by anything. The template is
a tracked, copy-and-run `.py` that sits outside the admission declaration's
coverage clause (`tools/admission_root_v1.py`'s `tracked_python` predicate
covers only top-level, `aec/`, `tests/`, and `tools/` paths), so it carries no
frozen digest -- it could break with admission green and the suite green. That
is not a hypothetical: step 5 of the doc shipped in a state where it could
never pass, because `checkpoint` compared the consumer's state against AEC's
own HEAD.

So these tests do not read the doc. They build a throwaway consumer
repository, perform exactly the edits the doc names, execute the template, and
run the documented verification command. `ReachesARenderedCardTests` is the
walkthrough; `RejectsAMisboundRevisionTests` pins the defect that made the
walkthrough impossible, so dropping `--project-root` from `checkpoint` -- or
defaulting it to the consumer root and thereby unbinding AEC's own use --
reds here rather than in a consumer's terminal.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "consumer-kit" / "state_producer_template.py"
REGISTER_HOOK_DOC = ROOT / "docs" / "consumer-kit" / "register-hook.md"

# The placeholder the template ships with and refuses to run against. Named
# here so that renaming it in the template reds this file instead of silently
# disabling the guard's test.
PLACEHOLDER_PROJECT = "your-owner/your-repository"


def run(*command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run one command exactly as a consumer would, capturing both streams."""
    return subprocess.run(
        list(command), check=False, cwd=cwd, capture_output=True, text=True
    )


def git(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], check=True, cwd=cwd, capture_output=True, text=True
    )


def make_consumer_repository(base: Path) -> Path:
    """Create a real, committed consumer repository with its own HEAD.

    A fresh repository is the point: its HEAD is necessarily different from
    AEC's, which is the exact condition step 5 has to survive.
    """
    repository = base / "consumer"
    (repository / "scripts").mkdir(parents=True)
    (repository / "app.py").write_text("consumer source\n", encoding="utf-8")
    git("init", "--quiet", cwd=repository)
    git("config", "user.email", "kit@example.invalid", cwd=repository)
    git("config", "user.name", "Install Kit Test", cwd=repository)
    (repository / ".gitignore").write_text("tmp/\n.local/\n", encoding="utf-8")
    git("add", "app.py", ".gitignore", cwd=repository)
    git("commit", "--quiet", "--message", "consumer initial commit", cwd=repository)
    return repository


def install_template(
    repository: Path,
    *,
    project: str = "kit-owner/kit-consumer",
    aec_checkout: str | None = None,
) -> Path:
    """Copy the template to `scripts/aec_state.py` and make the documented edits.

    `AEC_CHECKOUT` is pointed at this working tree rather than at a clone on
    purpose. A `git clone` would carry the last commit, so a defect introduced
    in the working tree would pass here and only red after being pushed --
    which is precisely the class of gap this file exists to close.
    """
    source = TEMPLATE.read_text(encoding="utf-8")
    checkout = str(ROOT) if aec_checkout is None else aec_checkout
    edited = source.replace(
        'AEC_CHECKOUT = Path(".local/aec")', f"AEC_CHECKOUT = Path({checkout!r})"
    ).replace(
        f'CONSUMER_PROJECT = "{PLACEHOLDER_PROJECT}"',
        f"CONSUMER_PROJECT = {project!r}",
    ).replace(
        'PROFILE_VERSION = "your-repository:1.0.0"',
        'PROFILE_VERSION = "kit-consumer:1.0.0"',
    )
    if aec_checkout is None:
        assert edited != source, "template constants no longer match the documented edits"
    destination = repository / "scripts" / "aec_state.py"
    destination.write_text(edited, encoding="utf-8")
    return destination


def head_revision(repository: Path) -> str:
    return git("rev-parse", "HEAD", cwd=repository).stdout.strip()


class TemplateProducesConsumerBoundStateTests(unittest.TestCase):
    """Step 2: the copied template runs and binds state to the consumer's HEAD."""

    def test_the_template_writes_state_bound_to_the_consumer_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = make_consumer_repository(Path(directory))
            install_template(repository)
            result = run(
                sys.executable,
                "scripts/aec_state.py",
                "--task",
                "myrepo#12",
                "--phase",
                "Framing",
                "--lane",
                "FEATURE",
                cwd=repository,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            state_path = repository / "tmp" / "aec-state.json"
            self.assertTrue(state_path.is_file(), "no state file was written")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(head_revision(repository), state["revision"]["identity"])
            self.assertNotEqual(head_revision(ROOT), state["revision"]["identity"])
            self.assertEqual(
                "kit-owner/kit-consumer", state["consumer_profile"]["project"]
            )
            self.assertTrue(state["policy"]["facts"]["require_exact_revision"])

    def test_the_unedited_template_refuses_to_run(self) -> None:
        """The doc marks CONSUMER_PROJECT required; the template enforces it."""
        with tempfile.TemporaryDirectory() as directory:
            repository = make_consumer_repository(Path(directory))
            install_template(repository, project=PLACEHOLDER_PROJECT)
            result = run(
                sys.executable,
                "scripts/aec_state.py",
                "--task",
                "myrepo#12",
                "--phase",
                "Framing",
                "--lane",
                "FEATURE",
                cwd=repository,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("set CONSUMER_PROJECT", result.stderr)
            self.assertFalse((repository / "tmp" / "aec-state.json").exists())

    def test_a_wrong_checkout_path_names_the_line_to_fix(self) -> None:
        """A misresolved AEC_ROOT must not surface as bare ModuleNotFoundError."""
        with tempfile.TemporaryDirectory() as directory:
            repository = make_consumer_repository(Path(directory))
            install_template(repository, aec_checkout=".local/aec")
            result = run(
                sys.executable,
                "scripts/aec_state.py",
                "--task",
                "myrepo#12",
                "--phase",
                "Framing",
                "--lane",
                "FEATURE",
                cwd=repository,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("no AEC checkout at", result.stderr)
            self.assertIn("AEC_CHECKOUT", result.stderr)


class ReachesARenderedCardTests(unittest.TestCase):
    """Step 5: the documented verification command reaches a human card."""

    def test_the_documented_verification_command_renders_a_card(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = make_consumer_repository(Path(directory))
            install_template(repository)
            produced = run(
                sys.executable,
                "scripts/aec_state.py",
                "--task",
                "myrepo#12",
                "--phase",
                "Framing",
                "--lane",
                "FEATURE",
                cwd=repository,
            )
            self.assertEqual(0, produced.returncode, produced.stderr)
            checkpoint = run(
                sys.executable,
                str(ROOT / "tools" / "aec_coach.py"),
                "checkpoint",
                "--project-root",
                str(repository),
                str(repository / "tmp" / "aec-state.json"),
                cwd=repository,
            )
            self.assertEqual(0, checkpoint.returncode, checkpoint.stderr)
            self.assertIn("[AEC: Project Guidance]", checkpoint.stdout)
            self.assertIn("[AEC: Mentoring]", checkpoint.stdout)


class RejectsAMisboundRevisionTests(unittest.TestCase):
    """Red canary for the defect that made step 5 impossible to pass.

    Without `--project-root`, `checkpoint` proves AEC's own HEAD, so a
    consumer state -- which is bound to the consumer's HEAD by design -- can
    never match. Both directions are pinned: the consumer path must need the
    flag's revision, and AEC's own default must stay AEC's own checkout.
    """

    def test_omitting_project_root_rejects_a_consumer_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = make_consumer_repository(Path(directory))
            install_template(repository)
            run(
                sys.executable,
                "scripts/aec_state.py",
                "--task",
                "myrepo#12",
                "--phase",
                "Framing",
                "--lane",
                "FEATURE",
                cwd=repository,
            )
            checkpoint = run(
                sys.executable,
                str(ROOT / "tools" / "aec_coach.py"),
                "checkpoint",
                str(repository / "tmp" / "aec-state.json"),
                cwd=repository,
            )
            self.assertNotEqual(0, checkpoint.returncode)
            self.assertEqual("", checkpoint.stdout)
            self.assertIn("CONSUMER_STATE_MISMATCH", checkpoint.stderr)

    def test_project_root_still_rejects_a_state_from_another_revision(self) -> None:
        """The flag supplies a revision; it never relaxes the comparison."""
        with tempfile.TemporaryDirectory() as directory:
            repository = make_consumer_repository(Path(directory))
            install_template(repository)
            run(
                sys.executable,
                "scripts/aec_state.py",
                "--task",
                "myrepo#12",
                "--phase",
                "Framing",
                "--lane",
                "FEATURE",
                cwd=repository,
            )
            (repository / "app.py").write_text("moved on\n", encoding="utf-8")
            git("add", "app.py", cwd=repository)
            git("commit", "--quiet", "--message", "consumer moves on", cwd=repository)
            checkpoint = run(
                sys.executable,
                str(ROOT / "tools" / "aec_coach.py"),
                "checkpoint",
                "--project-root",
                str(repository),
                str(repository / "tmp" / "aec-state.json"),
                cwd=repository,
            )
            self.assertNotEqual(0, checkpoint.returncode)
            self.assertEqual("", checkpoint.stdout)
            self.assertIn("CONSUMER_STATE_MISMATCH", checkpoint.stderr)


class DocumentedCommandsMatchTheToolTests(unittest.TestCase):
    """The doc must not send a consumer after a string the tool cannot emit."""

    def test_step_five_documents_the_project_root_flag(self) -> None:
        text = REGISTER_HOOK_DOC.read_text(encoding="utf-8")
        self.assertIn("--project-root", text)

    def test_the_doc_ignores_the_vendored_checkout(self) -> None:
        """`.local/` must be ignored, or `git add -A` commits an embedded repo."""
        text = REGISTER_HOOK_DOC.read_text(encoding="utf-8")
        self.assertIn(".local/", text)

    def test_the_doc_does_not_attribute_the_hook_signature_to_checkpoint(self) -> None:
        """`[AEC: Integration Blocked]` comes from the prompt hook alone."""
        coach = (ROOT / "tools" / "aec_coach.py").read_text(encoding="utf-8")
        self.assertNotIn("[AEC: Integration Blocked]", coach)
        text = REGISTER_HOOK_DOC.read_text(encoding="utf-8")
        blocked_index = text.find("[AEC: Integration Blocked]")
        self.assertNotEqual(-1, blocked_index, "the doc should still explain the signal")
        self.assertIn(
            "different",
            text[blocked_index : blocked_index + 200],
            "the doc must distinguish the hook signal from checkpoint's exit code",
        )


if __name__ == "__main__":
    unittest.main()
