#!/usr/bin/env python3
"""Prove real Claude and Codex loader parity without model-generated claims."""

from __future__ import annotations

import json
import os
import pty
import select
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aec.adapters import (  # noqa: E402
    AdapterRejection,
    AdapterReceipt,
    build_adapter_receipt,
    codex_nonproject_conflicts,
    parse_claude_loader_log,
    parse_codex_prompt_input,
)
from tools.validate_blueprint_skills import (  # noqa: E402
    validate_blueprint_installation,
)


class ProofError(RuntimeError):
    """Raised when live adapter proof cannot establish a trusted receipt."""


def _run_text(command: list[str], *, timeout: float = 20.0) -> str:
    """Run one read-only command and return its stripped standard output."""
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ProofError(f"command failed: {command[0]}") from error
    return completed.stdout.strip()


def _codex_prompt_input(config: str | None = None) -> object:
    """Collect one model-free Codex prompt-input payload."""
    command = ["codex", "debug", "prompt-input"]
    if config is not None:
        command.extend(["-c", config])
    command.append("Use the milestone skill.")
    raw_payload = _run_text(command)
    try:
        return json.loads(raw_payload)
    except json.JSONDecodeError as error:
        raise ProofError("Codex prompt-input output is not valid JSON") from error


def _collect_codex() -> tuple[object, str, int]:
    """Collect Codex model-free prompt-input loader evidence."""
    version = _run_text(["codex", "--version"])
    preflight = _codex_prompt_input()
    conflicts = codex_nonproject_conflicts(preflight, project_root=ROOT)
    if isinstance(conflicts, AdapterRejection):
        raise ProofError(f"Codex conflict preflight failed: {conflicts.code}")
    if not conflicts:
        return preflight, version, 0
    rules = ", ".join(
        f'{{path={json.dumps(path)}, enabled=false}}' for path in conflicts
    )
    filtered = _codex_prompt_input(f"skills.config=[{rules}]")
    return filtered, version, len(conflicts)


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Stop the loader-only Claude process and all children."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=1)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)


def _collect_claude(timeout: float = 15.0) -> tuple[str, str]:
    """Collect Claude project-loader debug evidence before any model prompt."""
    version = _run_text(["claude", "--version"])
    with tempfile.TemporaryDirectory(prefix="aec-claude-loader-") as temporary:
        debug_path = Path(temporary) / "loader.log"
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(
                [
                    "claude",
                    "--debug-file",
                    str(debug_path),
                    "--setting-sources",
                    "project",
                    "--tools",
                    "",
                    "--no-chrome",
                ],
                cwd=ROOT,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                close_fds=True,
                start_new_session=True,
            )
        except OSError as error:
            os.close(master)
            os.close(slave)
            raise ProofError("command failed: claude") from error
        os.close(slave)
        deadline = time.monotonic() + timeout
        log_text = ""
        try:
            while time.monotonic() < deadline:
                readable, _, _ = select.select([master], [], [], 0.05)
                if readable:
                    try:
                        os.read(master, 65536)
                    except OSError:
                        break
                if debug_path.exists():
                    log_text = debug_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                    if "getSkills returning:" in log_text:
                        break
                if process.poll() is not None:
                    break
        finally:
            _stop_process(process)
            os.close(master)
        if "getSkills returning:" not in log_text:
            raise ProofError("Claude project loader did not emit complete evidence")
        return log_text, version


def _load_json(path: Path) -> object:
    """Load one trusted repository JSON input."""
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProofError(f"invalid proof input: {path.relative_to(ROOT)}") from error


def _require_ready(receipt: AdapterReceipt) -> None:
    """Reject any receipt that does not prove authoritative adapter readiness."""
    if receipt.status != "ready" or not receipt.authoritative:
        raise ProofError(f"{receipt.agent} adapter proof failed: {receipt.code}")


def prove() -> dict[str, object]:
    """Return metadata-only live parity proof from both installed runtimes."""
    request = _load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
    catalog = _load_json(ROOT / "config/procedures/ticket-to-pr.json")
    manifest = _load_json(ROOT / "provenance/blueprint-skills.json")
    installation_errors = tuple(validate_blueprint_installation(ROOT))

    codex_payload, codex_version, codex_suppressed = _collect_codex()
    claude_log, claude_version = _collect_claude()
    codex_evidence = parse_codex_prompt_input(
        codex_payload,
        runtime_version=codex_version,
        project_root=ROOT,
        suppressed_conflicts=codex_suppressed,
    )
    claude_evidence = parse_claude_loader_log(
        claude_log,
        runtime_version=claude_version,
        project_root=ROOT,
    )
    codex_receipt = build_adapter_receipt(
        codex_evidence,
        request,
        catalog,
        manifest,
        installation_errors=installation_errors,
    )
    claude_receipt = build_adapter_receipt(
        claude_evidence,
        request,
        catalog,
        manifest,
        installation_errors=installation_errors,
    )
    _require_ready(codex_receipt)
    _require_ready(claude_receipt)
    parity_fields = ("decision_hash", "request_hash", "skill_manifest_hash")
    if any(
        getattr(codex_receipt, field) != getattr(claude_receipt, field)
        for field in parity_fields
    ):
        raise ProofError("Claude and Codex adapter receipt bindings differ")
    return {
        "agents": [codex_receipt.to_dict(), claude_receipt.to_dict()],
        "decision_hash_equal": True,
        "model_requests": 0,
        "mutates": False,
        "schema_version": "1.0.0",
        "status": "PASS",
    }


def main() -> int:
    """Print one metadata-only parity proof or fail closed."""
    try:
        result = prove()
    except ProofError as error:
        print(
            json.dumps(
                {
                    "code": "ADAPTER_PARITY_UNPROVEN",
                    "error": str(error),
                    "status": "FAIL",
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
