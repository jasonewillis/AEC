#!/usr/bin/env python3
"""Render one validated AEC card at an agent prompt-hook boundary.

The hook reads a Claude-compatible ``UserPromptSubmit`` payload from standard
input, but never derives lifecycle state from prompt text. It reads one
consumer-owned state file, binds validation to the consumer repository's exact
HEAD and configured environment, and emits the normal AEC human renderer.

Integration failures remain non-blocking for the host prompt while becoming
visible in its context. They never render a workflow rail.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aec.consumer import ConsumerStateRejection, resolve_consumer_state
from aec.human_render import (
    INTERACTION_TRIGGERS,
    RenderFailure,
    default_rail_definition,
    render_interaction,
)


ROOT = Path(__file__).resolve().parents[1]
PROCEDURE_CATALOG_PATH = ROOT / "config" / "procedures" / "ticket-to-pr.json"
BLOCKED_HEADING = "[AEC: Integration Blocked]"
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")


class HookFailure(RuntimeError):
    """One stable, fail-visible prompt-hook rejection."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def load_object(path: Path, code: str) -> dict[str, Any]:
    """Load one JSON object without exposing local paths or input bytes."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise HookFailure(code) from error
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        failure_code = "STATE_INVALID" if code == "STATE_UNAVAILABLE" else code
        raise HookFailure(failure_code) from error
    if type(value) is not dict:
        raise HookFailure("STATE_INVALID" if code == "STATE_UNAVAILABLE" else code)
    return value


def read_hook_payload() -> str:
    """Require the real Claude prompt-hook payload shape.

    Prompt text is intentionally discarded. A consumer-owned adapter may add
    ``aec_trigger`` as the closed, per-interaction presentation signal. Native
    hook payloads omit it and therefore receive compact routine output.
    """
    try:
        payload = json.loads(sys.stdin.read())
    except (OSError, json.JSONDecodeError) as error:
        raise HookFailure("HOOK_INPUT_REJECTED") from error
    if (
        type(payload) is not dict
        or payload.get("hook_event_name") != "UserPromptSubmit"
        or type(payload.get("prompt")) is not str
    ):
        raise HookFailure("HOOK_INPUT_REJECTED")
    trigger = payload.get("aec_trigger", "routine-progress")
    if type(trigger) is not str or trigger not in INTERACTION_TRIGGERS:
        raise HookFailure("HOOK_INPUT_REJECTED")
    return trigger


def current_revision(project_root: Path) -> str:
    """Return the exact consumer HEAD used to validate the state."""
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise HookFailure("PROJECT_REVISION_UNAVAILABLE") from error
    revision = result.stdout.strip()
    if result.returncode != 0 or HEX_REVISION.fullmatch(revision) is None:
        raise HookFailure("PROJECT_REVISION_UNAVAILABLE")
    return revision


def utc_now() -> str:
    """Return current UTC in the consumer contract's required format."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.isoformat().replace("+00:00", "Z")


def resolve_state_path(state: Path | None, project_root: Path) -> Path:
    """Resolve explicit CLI, environment, or conventional ignored state."""
    selected = state
    if selected is None:
        configured = os.environ.get("AEC_STATE_PATH")
        selected = Path(configured) if configured else Path("tmp/aec-state.json")
    return selected if selected.is_absolute() else project_root / selected


def render_checkpoint(
    state_path: Path, project_root: Path, environment: str, trigger: str
) -> str:
    """Validate and render one state without executing its transition draft."""
    state = load_object(state_path, "STATE_UNAVAILABLE")
    catalog = load_object(PROCEDURE_CATALOG_PATH, "CATALOG_UNAVAILABLE")
    revision = current_revision(project_root)
    result = resolve_consumer_state(
        state,
        catalog,
        current_time=utc_now(),
        expected_environment=environment,
        expected_revision=revision,
    )
    if isinstance(result, ConsumerStateRejection):
        raise HookFailure(f"STATE_REJECTED:{result.code}")
    if current_revision(project_root) != revision:
        raise HookFailure("PROJECT_REVISION_CHANGED")
    try:
        return render_interaction(
            result.to_dict(),
            default_rail_definition(),
            trigger,
            evidence=state["evidence"],
            blockers=state["blockers"],
            task_id=state["task"]["identity"],
        )
    except (KeyError, TypeError, ValueError, RenderFailure) as error:
        raise HookFailure("RENDER_REJECTED") from error


def blocked_output(code: str) -> str:
    """Return a stable context message and deliberately omit any rail."""
    return (
        f"{BLOCKED_HEADING}\n"
        f"Code: {code}\n"
        "AEC cannot prove the current lifecycle position from validated "
        "consumer state. No workflow rail or mentoring recommendation was rendered.\n"
    )


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse prompt-hook configuration owned by the consumer."""
    parser = argparse.ArgumentParser(prog="aec-prompt-hook", description=__doc__)
    parser.add_argument("--state", type=Path)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd())),
    )
    parser.add_argument(
        "--environment", default=os.environ.get("AEC_ENVIRONMENT", "local")
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Render valid coaching or one fail-visible integration block."""
    arguments = parse_arguments(argv)
    project_root = arguments.project_root.resolve()
    state_path = resolve_state_path(arguments.state, project_root)
    try:
        trigger = read_hook_payload()
        rendered = render_checkpoint(
            state_path, project_root, arguments.environment, trigger
        )
    except HookFailure as error:
        rendered = blocked_output(error.code)
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
