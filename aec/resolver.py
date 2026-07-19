"""Pure deterministic mentoring-decision resolver."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


def canonical_resolution_bytes(resolution: object) -> bytes:
    """Return canonical UTF-8 bytes covered by a decision hash."""
    if not isinstance(resolution, dict):
        raise TypeError("resolution must be an object")
    payload = {
        key: value for key, value in resolution.items() if key != "resolution_hash"
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return serialized.encode("utf-8")


def compute_resolution_hash(resolution: object) -> str:
    """Compute the SHA-256 identifier for a normalized mentoring decision."""
    digest = hashlib.sha256(canonical_resolution_bytes(resolution)).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class ResolutionDecision:
    """Immutable canonical representation of one mentoring decision."""

    canonical_bytes: bytes
    hashed_bytes: bytes
    resolution_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible representation of the decision."""
        payload = json.loads(self.canonical_bytes)
        if not isinstance(payload, dict):
            raise TypeError("canonical decision must decode to an object")
        return payload


def _accepted_evidence(request: dict[str, Any]) -> set[str]:
    """Return evidence kinds accepted for the request revision and environment."""
    revision = request["revision"]
    environment = request["environment"]
    return {
        fact["kind"]
        for fact in request["evidence"]
        if fact.get("accepted") is True
        and fact.get("revision") == revision
        and fact.get("environment") == environment
    }


def resolve(request: object, procedures: object) -> ResolutionDecision:
    """Resolve one normalized request without discovery, I/O, or mutation."""
    if not isinstance(request, dict) or not isinstance(procedures, dict):
        raise TypeError("request and procedures must be objects")

    available = {
        (item["identity"], item["revision"])
        for item in request["available_procedures"]
        if isinstance(item, dict)
    }
    phase_procedures = [
        procedure
        for procedure in procedures["procedures"]
        if isinstance(procedure, dict)
        and procedure.get("phase") == request["phase"]
    ]
    matches = [
        procedure
        for procedure in phase_procedures
        if (procedure.get("identity"), procedure.get("revision")) in available
    ]
    if len(matches) > 1 or (not matches and len(phase_procedures) != 1):
        raise ValueError("normalized request must resolve exactly one procedure")

    skill_unavailable = not matches
    procedure = phase_procedures[0] if skill_unavailable else matches[0]
    accepted_evidence = _accepted_evidence(request)
    required_evidence = [
        kind for kind in procedure["required_evidence"] if kind not in accepted_evidence
    ]
    allowed = True
    anti_example = procedure["anti_example"]
    finished = procedure["finished"]
    gate = "Evidence needed" if required_evidence else "Ready"
    good = procedure["good"]
    rationale = procedure["rationale"]
    reason_code = (
        procedure["reason_code"]
        if required_evidence
        else "ACCEPTANCE_EVIDENCE_COMPLETE"
    )
    if skill_unavailable:
        allowed = False
        anti_example = "Another available procedure is silently substituted."
        finished = ["The required procedure is available at its pinned revision."]
        gate = "Blocked"
        good = ["The required procedure is available before it is recommended."]
        rationale = {
            "principle_ids": procedure["rationale"]["principle_ids"],
            "summary": "The required procedure is unavailable for the requested phase.",
        }
        reason_code = "SKILL_UNAVAILABLE"
        required_evidence = []
    workflow = request["workflow"]
    capability_profile = request["capability_profile"]
    consumer_profile = request["consumer_profile"]
    policy = request["policy"]
    payload = {
        "allowed": allowed,
        "anti_example": anti_example,
        "capability_profile_version": capability_profile["version"],
        "environment": request["environment"],
        "executes": False,
        "finished": finished,
        "gate": gate,
        "good": good,
        "lane": request["lane"],
        "mutates": False,
        "phase": request["phase"],
        "policy_version": policy["revision"],
        "primary_procedure": procedure["identity"],
        "project_profile_version": consumer_profile["version"],
        "rationale": rationale,
        "reason_code": reason_code,
        "required_evidence": required_evidence,
        "revision": request["revision"],
        "schema_version": "1.0.0",
        "source_identities": {
            "capability_profile": capability_profile["identity"],
            "consumer_profile": consumer_profile["identity"],
            "policy": policy["identity"],
            "procedure": procedure["identity"],
            "workflow": workflow["identity"],
        },
        "source_revisions": {
            "capability_profile": capability_profile["version"],
            "consumer_profile": consumer_profile["version"],
            "policy": policy["revision"],
            "procedure": procedure["revision"],
            "workflow": workflow["revision"],
        },
        "task_id": request["task_id"],
        "workflow": workflow["identity"],
        "workflow_stage": workflow["stage"],
    }
    resolution_hash = compute_resolution_hash(payload)
    payload["resolution_hash"] = resolution_hash
    canonical_bytes = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return ResolutionDecision(
        canonical_bytes=canonical_bytes,
        hashed_bytes=canonical_resolution_bytes(payload),
        resolution_hash=resolution_hash,
    )
