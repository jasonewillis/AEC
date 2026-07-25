"""Closed structural and tamper validation for the public AEC mentoring card.

`card_hash` binds the card's own bytes. It detects a card that was truncated,
edited, or reassembled after rendering, and it is recomputed by every reader.
It is not a signature: anyone who can rewrite a card can also recompute the
hash, so it proves nothing about who produced the card or where it came from.
AEC adds no signing keys and no secrets.
"""

from __future__ import annotations

import hashlib
import json
import re

from aec.contracts import normalize_exact_json
from aec.mentoring import validate_decision_context, validate_mentoring


PUBLIC_CARD_SCHEMA_VERSION = "3.0.0"
PUBLIC_CARD_FIELDS = {
    "anti_example",
    "authoritative",
    "card_hash",
    "decision_support",
    "finished",
    "gate",
    "good",
    "lane",
    "mentoring",
    "phase",
    "rail_position",
    "rationale",
    "required_proof",
    "resolution_hash",
    "schema_version",
    "transition_request",
}
RAIL_POSITION_FIELDS = {"phase", "phase_total", "rail", "rail_total", "stage"}
RATIONALE_FIELDS = {"principle_ids", "summary"}
TRANSITION_REQUEST_FIELDS = {
    "authoritative",
    "environment",
    "executes",
    "mutates",
    "requested_gate",
    "revision",
}
GATES = {"Blocked", "Evidence needed", "Needs review", "Ready"}
PHASE_RAIL = (
    "Intake",
    "Framing",
    "Spec",
    "Plan",
    "Build",
    "Verify",
    "Review",
    "PR",
    "Deploy",
)
STAGE_PHASES = {
    "Understand": ("Intake", "Framing"),
    "Design": ("Spec", "Plan"),
    "Execute": ("Build", "Verify"),
    "Assure & Release": ("Review", "PR", "Deploy"),
}
CARD_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
RESOLUTION_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")


def compute_card_hash(card: object) -> str:
    """Return the deterministic hash of one complete card except card_hash."""
    payload = normalize_exact_json(card)
    if type(payload) is not dict:
        raise TypeError("public card must be an object")
    covered = {name: value for name, value in payload.items() if name != "card_hash"}
    canonical = json.dumps(
        covered,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8", errors="strict")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _non_empty_string(value: object) -> bool:
    """Return whether a value is an exact non-empty string."""
    return type(value) is str and bool(value.strip())


def _string_list(value: object) -> bool:
    """Return whether a value is a non-empty list of non-empty strings."""
    return (
        type(value) is list
        and bool(value)
        and all(_non_empty_string(item) for item in value)
    )


def _validate_rail_position(value: object, phase: object, field: str) -> list[str]:
    """Validate the rail position and its agreement with the rendered phase."""
    if type(value) is not dict or set(value) != RAIL_POSITION_FIELDS:
        return [f"{field} fields do not match the contract"]
    stage = value.get("stage")
    if stage not in STAGE_PHASES:
        return [f"{field}.stage is unsupported"]
    stage_phases = STAGE_PHASES[stage]
    if phase not in stage_phases:
        return [f"{field}.stage does not contain the rendered phase"]
    expected = {
        "phase": stage_phases.index(phase) + 1,
        "phase_total": len(stage_phases),
        "rail": PHASE_RAIL.index(phase) + 1,
        "rail_total": len(PHASE_RAIL),
        "stage": stage,
    }
    return [] if value == expected else [f"{field} does not match the rendered phase"]


def _validate_transition_request(value: object, gate: object, field: str) -> list[str]:
    """Validate the non-authoritative draft transition the card carries."""
    if type(value) is not dict or set(value) != TRANSITION_REQUEST_FIELDS:
        return [f"{field} fields do not match the contract"]
    errors: list[str] = []
    for name in ("authoritative", "executes", "mutates"):
        if value.get(name) is not False:
            errors.append(f"{field}.{name} must be false")
    if not _non_empty_string(value.get("environment")):
        errors.append(f"{field}.environment must be a non-empty string")
    revision = value.get("revision")
    if type(revision) is not str or not HEX_REVISION.fullmatch(revision):
        errors.append(f"{field}.revision must be a lowercase 40-character Git commit")
    if value.get("requested_gate") != gate:
        errors.append(f"{field}.requested_gate must equal the rendered gate")
    return errors


def validate_public_card(card: object, field: str = "card") -> list[str]:
    """Validate one complete public card and recompute its own card hash."""
    try:
        value = normalize_exact_json(card)
    except (TypeError, ValueError):
        return [f"{field} must contain only exact JSON values"]
    if type(value) is not dict or set(value) != PUBLIC_CARD_FIELDS:
        return [f"{field} fields do not match the contract"]

    errors: list[str] = []
    if value.get("schema_version") != PUBLIC_CARD_SCHEMA_VERSION:
        errors.append(f"{field}.schema_version must equal {PUBLIC_CARD_SCHEMA_VERSION}")
    if value.get("authoritative") is not False:
        errors.append(f"{field}.authoritative must be false")
    gate = value.get("gate")
    if gate not in GATES:
        errors.append(f"{field}.gate is unsupported")
    phase = value.get("phase")
    if phase not in PHASE_RAIL:
        errors.append(f"{field}.phase is unsupported")
    for name in ("anti_example", "lane"):
        if not _non_empty_string(value.get(name)):
            errors.append(f"{field}.{name} must be a non-empty string")
    for name in ("finished", "good"):
        if not _string_list(value.get(name)):
            errors.append(f"{field}.{name} must be a non-empty list of non-empty strings")
    # A Ready card requires no further proof, so an empty list is a real card.
    required_proof = value.get("required_proof")
    if type(required_proof) is not list or not all(
        _non_empty_string(item) for item in required_proof
    ):
        errors.append(f"{field}.required_proof must be a list of non-empty strings")
    resolution_hash = value.get("resolution_hash")
    if type(resolution_hash) is not str or not RESOLUTION_HASH.fullmatch(
        resolution_hash
    ):
        errors.append(f"{field}.resolution_hash must be a SHA-256 binding")

    rationale = value.get("rationale")
    if type(rationale) is not dict or set(rationale) != RATIONALE_FIELDS:
        errors.append(f"{field}.rationale fields do not match the contract")
    else:
        if not _string_list(rationale.get("principle_ids")):
            errors.append(f"{field}.rationale.principle_ids must be a string list")
        if not _non_empty_string(rationale.get("summary")):
            errors.append(f"{field}.rationale.summary must be a non-empty string")

    errors.extend(validate_mentoring(value.get("mentoring"), f"{field}.mentoring"))
    errors.extend(
        _validate_rail_position(
            value.get("rail_position"), phase, f"{field}.rail_position"
        )
    )
    transition = value.get("transition_request")
    errors.extend(
        _validate_transition_request(transition, gate, f"{field}.transition_request")
    )
    revision = transition.get("revision") if type(transition) is dict else None
    errors.extend(
        validate_decision_context(
            value.get("decision_support"),
            f"{field}.decision_support",
            revision=revision,
        )
    )

    card_hash = value.get("card_hash")
    if type(card_hash) is not str or not CARD_HASH.fullmatch(card_hash):
        errors.append(f"{field}.card_hash must be a SHA-256 binding")
    elif card_hash != compute_card_hash(value):
        errors.append(f"{field}.card_hash does not match the rendered card")
    return errors
