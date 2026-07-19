"""Pure deterministic mentoring-decision resolver."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from aec.contracts import validate_project_profile


REQUIRED_REQUEST_FIELDS = {
    "available_procedures",
    "blockers",
    "capability_profile",
    "consumer_profile",
    "environment",
    "evidence",
    "lane",
    "phase",
    "policy",
    "required_procedure",
    "revision",
    "schema_version",
    "task_id",
    "workflow",
}
REQUIRED_CATALOG_FIELDS = {"procedures", "schema_version"}
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
PROCEDURE_REVISION = re.compile(
    r"^[A-Za-z0-9_.-]+:[A-Za-z0-9][A-Za-z0-9_.-]*$"
)
PROCEDURE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PROCEDURE_FIELDS = {
    "anti_example",
    "finished",
    "good",
    "identity",
    "phase",
    "rationale",
    "reason_code",
    "required_evidence",
    "revision",
}
PHASES = {
    "Build",
    "Deploy",
    "Framing",
    "Intake",
    "Plan",
    "PR",
    "Review",
    "Spec",
    "Verify",
}
STAGE_PHASES = {
    "Assure & Release": {"Deploy", "PR", "Review"},
    "Design": {"Plan", "Spec"},
    "Execute": {"Build", "Verify"},
    "Understand": {"Framing", "Intake"},
}


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


def _canonical_json_bytes(value: object) -> bytes:
    """Return deterministic UTF-8 JSON bytes for a normalized input value."""
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _input_binding(value: object) -> str:
    """Return a SHA-256 binding for one normalized resolver input."""
    digest = hashlib.sha256(_canonical_json_bytes(value)).hexdigest()
    return f"sha256:{digest}"


def _sorted_json_items(values: list[Any]) -> list[Any]:
    """Sort semantically unordered JSON values by their canonical bytes."""
    return sorted(values, key=_canonical_json_bytes)


def _normalized_request_binding(request: dict[str, Any]) -> dict[str, Any]:
    """Normalize semantically unordered request collections for binding."""
    normalized = copy.deepcopy(request)
    normalized["available_procedures"] = _sorted_json_items(
        normalized["available_procedures"]
    )
    normalized["blockers"] = _sorted_json_items(normalized["blockers"])
    normalized["capability_profile"]["capabilities"] = sorted(
        normalized["capability_profile"]["capabilities"]
    )
    normalized["consumer_profile"]["agent_adapters"] = sorted(
        normalized["consumer_profile"]["agent_adapters"]
    )
    normalized["evidence"] = _sorted_json_items(normalized["evidence"])
    return normalized


def _normalized_catalog_binding(catalog: dict[str, Any]) -> dict[str, Any]:
    """Normalize semantically unordered catalog collections for binding."""
    normalized = copy.deepcopy(catalog)
    for procedure in normalized["procedures"]:
        procedure["rationale"]["principle_ids"] = sorted(
            procedure["rationale"]["principle_ids"]
        )
        procedure["required_evidence"] = sorted(procedure["required_evidence"])
    normalized["procedures"] = _sorted_json_items(normalized["procedures"])
    return normalized


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


@dataclass(frozen=True)
class ResolutionRejection:
    """Immutable fail-closed result for an invalid normalized request."""

    errors: tuple[str, ...]
    code: str = "RESOLUTION_REQUEST_INVALID"
    accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible representation of the rejection."""
        return {
            "accepted": self.accepted,
            "code": self.code,
            "errors": list(self.errors),
        }


def _validate_available_procedures(value: object) -> list[str]:
    """Return deterministic errors for normalized procedure references."""
    if not isinstance(value, list):
        return ["available_procedures must be a list"]

    errors: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != {"identity", "revision"}:
            errors.append(
                f"available_procedures[{index}] must contain exactly identity and revision"
            )
            continue
        if not all(isinstance(item[field], str) and item[field] for field in item):
            errors.append(
                f"available_procedures[{index}] values must be non-empty strings"
            )
    if not errors:
        references = [(item["identity"], item["revision"]) for item in value]
        if len(references) != len(set(references)):
            errors.append("available_procedures must contain unique references")
    return errors


def _validate_exact_object(
    value: object,
    field: str,
    required_fields: set[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate one nested object and return its typed value and errors."""
    if not isinstance(value, dict):
        return None, [f"{field} must be an object"]
    if set(value) != required_fields:
        return value, [f"{field} fields do not match the contract"]
    return value, []


def _validate_non_empty_string_fields(
    value: dict[str, Any],
    field: str,
    names: tuple[str, ...],
) -> list[str]:
    """Validate named fields as non-empty strings."""
    return [
        f"{field}.{name} must be a non-empty string"
        for name in names
        if not isinstance(value.get(name), str) or not value.get(name)
    ]


def _validate_blockers(value: object) -> list[str]:
    """Validate normalized blocker facts."""
    if not isinstance(value, list):
        return ["blockers must be a list"]
    errors: list[str] = []
    for index, blocker in enumerate(value):
        normalized, object_errors = _validate_exact_object(
            blocker,
            f"blockers[{index}]",
            {"active", "identity", "reason_code"},
        )
        errors.extend(object_errors)
        if normalized is None or object_errors:
            continue
        if not isinstance(normalized.get("active"), bool):
            errors.append(f"blockers[{index}].active must be a boolean")
        errors.extend(
            _validate_non_empty_string_fields(
                normalized,
                f"blockers[{index}]",
                ("identity", "reason_code"),
            )
        )
    return errors


def _validate_capability_profile(value: object) -> list[str]:
    """Validate a normalized capability profile."""
    profile, errors = _validate_exact_object(
        value,
        "capability_profile",
        {"capabilities", "identity", "version"},
    )
    if profile is None or errors:
        return errors
    errors.extend(
        _validate_non_empty_string_fields(
            profile,
            "capability_profile",
            ("identity", "version"),
        )
    )
    capabilities = profile.get("capabilities")
    if not isinstance(capabilities, list) or not all(
        isinstance(item, str) and item for item in capabilities
    ):
        errors.append("capability_profile.capabilities must be a string list")
    elif len(capabilities) != len(set(capabilities)):
        errors.append("capability_profile.capabilities must be unique")
    return errors


def _validate_evidence(value: object) -> list[str]:
    """Validate normalized evidence facts."""
    if not isinstance(value, list):
        return ["evidence must be a list"]
    errors: list[str] = []
    for index, fact in enumerate(value):
        normalized, object_errors = _validate_exact_object(
            fact,
            f"evidence[{index}]",
            {"accepted", "environment", "kind", "revision"},
        )
        errors.extend(object_errors)
        if normalized is None or object_errors:
            continue
        if not isinstance(normalized.get("accepted"), bool):
            errors.append(f"evidence[{index}].accepted must be a boolean")
        errors.extend(
            _validate_non_empty_string_fields(
                normalized,
                f"evidence[{index}]",
                ("environment", "kind"),
            )
        )
        revision = normalized.get("revision")
        if not isinstance(revision, str) or not HEX_REVISION.fullmatch(revision):
            errors.append(
                f"evidence[{index}].revision must be a lowercase 40-character Git commit"
            )
    return errors


def _validate_policy(value: object) -> list[str]:
    """Validate normalized policy facts."""
    policy, errors = _validate_exact_object(
        value,
        "policy",
        {"facts", "identity", "revision"},
    )
    if policy is None or errors:
        return errors
    errors.extend(
        _validate_non_empty_string_fields(policy, "policy", ("identity", "revision"))
    )
    facts, fact_errors = _validate_exact_object(
        policy.get("facts"),
        "policy.facts",
        {"require_exact_environment", "require_exact_revision"},
    )
    errors.extend(fact_errors)
    if facts is not None and not fact_errors:
        for name in ("require_exact_environment", "require_exact_revision"):
            if not isinstance(facts.get(name), bool):
                errors.append(f"policy.facts.{name} must be a boolean")
    return errors


def _validate_procedure_reference(value: object, field: str) -> list[str]:
    """Validate one pinned procedure reference."""
    reference, errors = _validate_exact_object(
        value,
        field,
        {"identity", "revision"},
    )
    if reference is not None and not errors:
        errors.extend(
            _validate_non_empty_string_fields(
                reference,
                field,
                ("identity", "revision"),
            )
        )
    return errors


def _validate_workflow(value: object, phase: object) -> list[str]:
    """Validate one normalized workflow reference and stage mapping."""
    workflow, errors = _validate_exact_object(
        value,
        "workflow",
        {"identity", "revision", "stage"},
    )
    if workflow is None or errors:
        return errors
    errors.extend(
        _validate_non_empty_string_fields(
            workflow,
            "workflow",
            ("identity", "revision"),
        )
    )
    stage = workflow.get("stage")
    if not isinstance(stage, str) or stage not in STAGE_PHASES:
        errors.append("workflow.stage is unsupported")
    elif (
        isinstance(phase, str) and phase in PHASES and phase not in STAGE_PHASES[stage]
    ):
        errors.append("phase does not belong to workflow.stage")
    return errors


def validate_resolution_request(request: object) -> list[str]:
    """Return fail-closed validation errors for a normalized request."""
    if not isinstance(request, dict):
        return ["request must be an object"]
    if not all(isinstance(key, str) for key in request):
        return ["request field names must be strings"]

    keys = set(request)
    missing = sorted(REQUIRED_REQUEST_FIELDS - keys)
    unknown = sorted(keys - REQUIRED_REQUEST_FIELDS)
    errors: list[str] = []
    if missing:
        errors.append(f"missing request fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"unknown request fields: {', '.join(unknown)}")
    errors.extend(_validate_available_procedures(request.get("available_procedures")))
    errors.extend(_validate_blockers(request.get("blockers")))
    errors.extend(_validate_capability_profile(request.get("capability_profile")))
    errors.extend(
        f"consumer_profile: {error}"
        for error in validate_project_profile(request.get("consumer_profile"))
    )
    for field in ("environment", "lane", "task_id"):
        value = request.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{field} must be a non-empty string")
    phase = request.get("phase")
    if "phase" in request and (not isinstance(phase, str) or phase not in PHASES):
        errors.append("phase is unsupported")
    errors.extend(_validate_evidence(request.get("evidence")))
    errors.extend(_validate_policy(request.get("policy")))
    errors.extend(
        _validate_procedure_reference(
            request.get("required_procedure"),
            "required_procedure",
        )
    )
    revision = request.get("revision")
    if not isinstance(revision, str) or not HEX_REVISION.fullmatch(revision):
        errors.append("revision must be a lowercase 40-character Git commit")
    if request.get("schema_version") != "2.0.0":
        errors.append("schema_version must equal 2.0.0")
    errors.extend(_validate_workflow(request.get("workflow"), phase))
    return errors


def validate_procedure_catalog(catalog: object) -> list[str]:
    """Return fail-closed validation errors for a procedure catalog."""
    if not isinstance(catalog, dict):
        return ["procedure catalog must be an object"]
    if not all(isinstance(key, str) for key in catalog):
        return ["procedure catalog field names must be strings"]

    keys = set(catalog)
    missing = sorted(REQUIRED_CATALOG_FIELDS - keys)
    unknown = sorted(keys - REQUIRED_CATALOG_FIELDS)
    errors: list[str] = []
    if missing:
        errors.append(f"missing procedure catalog fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"unknown procedure catalog fields: {', '.join(unknown)}")
    if "schema_version" in catalog and catalog.get("schema_version") != "1.0.0":
        errors.append("procedure catalog schema_version must equal 1.0.0")
    procedures = catalog.get("procedures")
    if "procedures" in catalog and not isinstance(procedures, list):
        errors.append("procedure catalog procedures must be a list")
    elif isinstance(procedures, list):
        if not procedures:
            errors.append("procedure catalog procedures must not be empty")
        references: list[tuple[str, str]] = []
        for index, procedure in enumerate(procedures):
            field = f"procedures[{index}]"
            if not isinstance(procedure, dict) or set(procedure) != PROCEDURE_FIELDS:
                errors.append(f"{field} fields do not match the contract")
                continue
            errors.extend(
                _validate_non_empty_string_fields(
                    procedure,
                    field,
                    ("anti_example", "identity", "revision"),
                )
            )
            phase = procedure.get("phase")
            if not isinstance(phase, str) or phase not in PHASES:
                errors.append(f"{field}.phase is unsupported")
            if procedure.get("reason_code") != "ACCEPTANCE_EVIDENCE_INCOMPLETE":
                errors.append(
                    f"{field}.reason_code must equal ACCEPTANCE_EVIDENCE_INCOMPLETE"
                )
            for name in ("finished", "good", "required_evidence"):
                values = procedure.get(name)
                needs_value = name in {"finished", "good"}
                if (
                    not isinstance(values, list)
                    or (needs_value and not values)
                    or not all(isinstance(value, str) and value for value in values)
                ):
                    errors.append(f"{field}.{name} must be a normalized string list")
            rationale = procedure.get("rationale")
            if not isinstance(rationale, dict) or set(rationale) != {
                "principle_ids",
                "summary",
            }:
                errors.append(f"{field}.rationale fields do not match the contract")
            else:
                principle_ids = rationale.get("principle_ids")
                if (
                    not isinstance(principle_ids, list)
                    or not principle_ids
                    or not all(
                        isinstance(value, str) and value for value in principle_ids
                    )
                ):
                    errors.append(
                        f"{field}.rationale.principle_ids must be a normalized string list"
                    )
                summary = rationale.get("summary")
                if not isinstance(summary, str) or not summary:
                    errors.append(
                        f"{field}.rationale.summary must be a non-empty string"
                    )
            identity = procedure.get("identity")
            revision = procedure.get("revision")
            if (
                isinstance(identity, str)
                and identity
                and isinstance(revision, str)
                and revision
            ):
                prefix = f"{identity}:"
                version = revision[len(prefix) :] if revision.startswith(prefix) else ""
                if (
                    not PROCEDURE_REVISION.fullmatch(revision)
                    or not version
                    or not PROCEDURE_VERSION.fullmatch(version)
                ):
                    errors.append(f"{field}.revision must pin its identity and version")
                references.append((identity, revision))
        if len(references) != len(set(references)):
            errors.append("procedure catalog references must be unique")
    return errors


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


def resolve(
    request: object, procedures: object
) -> ResolutionDecision | ResolutionRejection:
    """Resolve one normalized request without discovery, I/O, or mutation."""
    request_errors = validate_resolution_request(request)
    if request_errors:
        return ResolutionRejection(tuple(request_errors))
    catalog_errors = validate_procedure_catalog(procedures)
    if catalog_errors:
        return ResolutionRejection(
            tuple(catalog_errors),
            code="PROCEDURE_CATALOG_INVALID",
        )

    assert isinstance(request, dict)
    assert isinstance(procedures, dict)

    input_bindings = {
        "procedure_catalog": _input_binding(_normalized_catalog_binding(procedures)),
        "resolution_request": _input_binding(_normalized_request_binding(request)),
    }

    available_procedures = sorted(
        (
            {"identity": item["identity"], "revision": item["revision"]}
            for item in request["available_procedures"]
            if isinstance(item, dict)
        ),
        key=lambda item: (item["identity"], item["revision"]),
    )
    available = {(item["identity"], item["revision"]) for item in available_procedures}
    required_procedure = request["required_procedure"]
    required_identity = (
        required_procedure["identity"],
        required_procedure["revision"],
    )
    matches = [
        procedure
        for procedure in procedures["procedures"]
        if isinstance(procedure, dict)
        and procedure.get("phase") == request["phase"]
        and (procedure.get("identity"), procedure.get("revision")) == required_identity
    ]
    if len(matches) != 1:
        return ResolutionRejection(
            ("required_procedure must identify exactly one catalog procedure",)
        )

    procedure = matches[0]
    skill_unavailable = required_identity not in available
    accepted_evidence = _accepted_evidence(request)
    required_evidence = sorted(
        kind for kind in procedure["required_evidence"] if kind not in accepted_evidence
    )
    allowed = True
    anti_example = procedure["anti_example"]
    finished = procedure["finished"]
    gate = "Evidence needed" if required_evidence else "Ready"
    good = procedure["good"]
    rationale = {
        "principle_ids": sorted(procedure["rationale"]["principle_ids"]),
        "summary": procedure["rationale"]["summary"],
    }
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
            "principle_ids": sorted(procedure["rationale"]["principle_ids"]),
            "summary": "The required procedure is unavailable for the requested phase.",
        }
        reason_code = "SKILL_UNAVAILABLE"
        required_evidence = ["procedure-availability"]
    workflow = request["workflow"]
    capability_profile = request["capability_profile"]
    consumer_profile = request["consumer_profile"]
    policy = request["policy"]
    payload = {
        "allowed": allowed,
        "anti_example": anti_example,
        "available_procedures": available_procedures,
        "capability_profile_version": capability_profile["version"],
        "environment": request["environment"],
        "executes": False,
        "finished": finished,
        "gate": gate,
        "good": good,
        "input_bindings": input_bindings,
        "lane": request["lane"],
        "mutates": False,
        "phase": request["phase"],
        "policy_version": policy["revision"],
        "primary_blocker": (
            {
                "identity": required_procedure["identity"],
                "reason_code": "SKILL_UNAVAILABLE",
            }
            if skill_unavailable
            else None
        ),
        "primary_procedure": None if skill_unavailable else procedure["identity"],
        "project_profile_version": consumer_profile["profile_version"],
        "rationale": rationale,
        "reason_code": reason_code,
        "required_evidence": required_evidence,
        "required_procedure": {
            "identity": required_procedure["identity"],
            "revision": required_procedure["revision"],
        },
        "revision": request["revision"],
        "schema_version": "3.0.0",
        "source_identities": {
            "capability_profile": capability_profile["identity"],
            "consumer_profile": consumer_profile["project"],
            "policy": policy["identity"],
            "procedure": procedure["identity"],
            "workflow": workflow["identity"],
        },
        "source_revisions": {
            "capability_profile": capability_profile["version"],
            "consumer_profile": consumer_profile["profile_version"],
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
