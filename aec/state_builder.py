"""Build one AEC coaching consumer state from framework-owned facts.

Ported from the HealthRAG pilot's `AEC/build_state.py` (issues #58, #52).
The pilot did its own file and Git I/O to prove a pin before trusting
anything; inside AEC there is no pin to prove, so this module keeps only
the pure construction logic and leaves I/O to `tools/aec_coach.py`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class BuildStateFailure(RuntimeError):
    """A fail-closed coaching state construction result."""


# AEC coaching itself: the framework is both mentor and, on its own backlog,
# consumer. `lifecycle_authority` stays "consumer-owned" because that is the
# only value validate_project_profile (aec/contracts.py) accepts -- it
# records that this never grants AEC execution authority over its own
# checkout.
AEC_SELF_PROFILE: dict[str, Any] = {
    "aec_mode": "read-only-mentor",
    "agent_adapters": ["claude-code", "codex"],
    "lifecycle_authority": "consumer-owned",
    "profile_version": "aec-self:1.0.0",
    "project": "jasonewillis/AEC",
    "schema_version": "1.0.0",
    "workflow": "ticket-to-pr",
}


def format_timestamp(moment: datetime) -> str:
    """Return one UTC RFC 3339 timestamp in the schema's required format."""
    return moment.isoformat().replace("+00:00", "Z")


def parse_evidence(raw: str) -> dict[str, str | bool]:
    """Parse one repeatable --evidence KIND[:accepted|:rejected] argument."""
    kind, separator, qualifier = raw.partition(":")
    if not kind:
        raise ValueError(f"--evidence kind must be non-empty: {raw!r}")
    if not separator:
        return {"kind": kind, "accepted": False}
    if qualifier == "accepted":
        return {"kind": kind, "accepted": True}
    if qualifier == "rejected":
        return {"kind": kind, "accepted": False}
    raise ValueError(f"--evidence qualifier must be accepted or rejected: {raw!r}")


def parse_blocker(raw: str) -> dict[str, str | bool]:
    """Parse one repeatable --blocker IDENTITY:REASON_CODE[:active|:inactive]."""
    identity, separator, remainder = raw.partition(":")
    if not identity or not separator:
        raise ValueError(
            f"--blocker must be IDENTITY:REASON_CODE[:active|:inactive]: {raw!r}"
        )
    reason_code, qualifier_separator, qualifier = remainder.partition(":")
    if not reason_code:
        raise ValueError(f"--blocker reason_code must be non-empty: {raw!r}")
    if not qualifier_separator:
        return {"active": True, "identity": identity, "reason_code": reason_code}
    if qualifier == "active":
        return {"active": True, "identity": identity, "reason_code": reason_code}
    if qualifier == "inactive":
        return {"active": False, "identity": identity, "reason_code": reason_code}
    raise ValueError(f"--blocker qualifier must be active or inactive: {raw!r}")


def procedure_references(
    catalog: dict[str, Any], phase: str
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Return the catalog's procedure references and the one required for phase."""
    procedures = catalog.get("procedures")
    if type(procedures) is not list:
        raise BuildStateFailure("procedure catalog is malformed")
    available: list[dict[str, str]] = []
    required: dict[str, str] | None = None
    for procedure in procedures:
        if type(procedure) is not dict:
            raise BuildStateFailure("procedure catalog entry is malformed")
        identity = procedure.get("identity")
        revision = procedure.get("revision")
        if type(identity) is not str or type(revision) is not str:
            raise BuildStateFailure("procedure catalog entry is malformed")
        reference = {"identity": identity, "revision": revision}
        available.append(reference)
        if procedure.get("phase") == phase:
            required = reference
    if required is None:
        raise BuildStateFailure(f"procedure catalog has no procedure for phase: {phase}")
    return available, required


def workflow_references(workflow: Any) -> tuple[dict[str, str], str, str]:
    """Derive the phase->stage map, workflow id, and revision from the workflow."""
    if not isinstance(workflow, dict):
        raise BuildStateFailure("workflow definition is not an object")
    identity = workflow.get("id")
    schema_version = workflow.get("schema_version")
    stages = workflow.get("stages")
    if not isinstance(identity, str) or not identity:
        raise BuildStateFailure("workflow definition has no id")
    if not isinstance(schema_version, str) or not schema_version:
        raise BuildStateFailure("workflow definition has no schema_version")
    if not isinstance(stages, list) or not stages:
        raise BuildStateFailure("workflow definition has no stages")

    phase_stage: dict[str, str] = {}
    for stage in stages:
        if not isinstance(stage, dict):
            raise BuildStateFailure("workflow stage is not an object")
        name = stage.get("name")
        phases = stage.get("phases")
        if not isinstance(name, str) or not isinstance(phases, list):
            raise BuildStateFailure("workflow stage has no name or phases")
        for phase in phases:
            if not isinstance(phase, str):
                raise BuildStateFailure("workflow phase is not a string")
            phase_stage[phase] = name
    if not phase_stage:
        raise BuildStateFailure("workflow definition declares no phases")
    return phase_stage, identity, f"{identity}:{schema_version}"


def build_state(
    *,
    task: str,
    phase: str,
    lane: str,
    environment: str,
    expires_minutes: int,
    evidence: list[dict[str, str | bool]],
    blockers: list[dict[str, str | bool]],
    revision: str,
    catalog: dict[str, Any],
    workflow: dict[str, Any],
    profile: dict[str, Any] | None = None,
    decision_context: dict[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Construct one schema-shaped consumer state, proving every derivable fact.

    Every argument that could vary between callers must be passed explicitly.
    Nothing is defaulted into existence except `profile`, which defaults to
    AEC coaching its own repository.
    """
    if not task:
        raise BuildStateFailure("task must be non-empty")
    if not lane:
        raise BuildStateFailure("lane must be non-empty")
    if not revision:
        raise BuildStateFailure("revision must be non-empty")

    phase_stage, workflow_identity, workflow_revision = workflow_references(workflow)
    if phase not in phase_stage:
        raise BuildStateFailure(f"unknown phase: {phase}")
    available, required = procedure_references(catalog, phase)

    observed = (observed_at or datetime.now(timezone.utc)).replace(microsecond=0)
    expires = observed + timedelta(minutes=expires_minutes)

    evidence_records = [
        {
            "accepted": bool(entry["accepted"]),
            "environment": environment,
            "kind": str(entry["kind"]),
            "revision": revision,
        }
        for entry in evidence
    ]

    blocker_records = [
        {
            "active": bool(entry["active"]),
            "identity": str(entry["identity"]),
            "reason_code": str(entry["reason_code"]),
        }
        for entry in blockers
    ]

    state: dict[str, Any] = {
        "blockers": blocker_records,
        "capabilities": {
            "capabilities": ["read-only-mentor"],
            "identity": "aec-coach-common",
            "version": "aec-coach-common:1.0.0",
        },
        "consumer_profile": profile if profile is not None else AEC_SELF_PROFILE,
        "effects": {"executes": False, "mutates": False},
        "environment": {"identity": environment},
        "evidence": evidence_records,
        "expires_at": format_timestamp(expires),
        "observed_at": format_timestamp(observed),
        "policy": {
            "facts": {
                "require_exact_environment": True,
                "require_exact_revision": True,
            },
            "identity": "aec-coach-delivery",
            "revision": "aec-coach-delivery:1.0.0",
        },
        "procedures": {"available": available, "required": required},
        "provider": {
            "identity": "aec-build-state",
            "revision": "aec-build-state:1.0.0",
        },
        "revision": {"identity": revision},
        "schema_version": "1.0.0",
        "task": {"identity": task},
        "workflow_position": {
            "lane": lane,
            "phase": phase,
            "stage": phase_stage[phase],
            "workflow": workflow_identity,
            "workflow_revision": workflow_revision,
        },
    }

    if decision_context is not None:
        state["decision_context"] = _bind_decision_context_revision(
            decision_context, revision
        )

    return state


def _bind_decision_context_revision(
    decision_context: dict[str, Any], revision: str
) -> dict[str, Any]:
    """Return decision_context with context.revision bound to the resolved revision.

    A caller cannot know the exact commit ahead of time, so its own
    `context.revision` is never trusted -- overwritten the same way
    evidence_records overwrite each entry's `revision` above.
    """
    context = decision_context.get("context")
    if not isinstance(context, dict):
        raise BuildStateFailure("decision context has no context object")
    bound = dict(decision_context)
    bound["context"] = {**context, "revision": revision}
    return bound
