"""Verify normalized offline review facts without granting authority."""

from __future__ import annotations

import json
from dataclasses import dataclass


_BINDING_FIELDS = (
    "subject_identity",
    "subject_revision",
    "baseline_revision",
    "review_identity",
    "issuer_identity",
    "receipt_digest",
    "evidence_digest",
    "signed_payload_digest",
    "signature_result_identity",
    "signer_identity",
    "signer_key_identity",
)
_EVIDENCE_FIELDS = frozenset((*_BINDING_FIELDS, "observations"))
_OBSERVATION_FIELDS = frozenset(
    (
        *_BINDING_FIELDS,
        "observation_identity",
        "order",
        "review_state",
        "signature_verified",
    )
)
_REVIEW_STATES = frozenset({"error", "failed", "pending", "verified"})


@dataclass(frozen=True, slots=True)
class OfflineReviewVerification:
    """Detached bindings for one internally consistent offline verification."""

    status: str
    subject_identity: str
    subject_revision: str
    baseline_revision: str
    review_identity: str
    issuer_identity: str
    receipt_digest: str
    evidence_digest: str
    signed_payload_digest: str
    signature_result_identity: str
    signer_identity: str
    signer_key_identity: str
    latest_observation_identity: str
    latest_order: int
    canonical_bytes: bytes


@dataclass(frozen=True, slots=True)
class OfflineReviewFailure:
    """One deterministic failure with no partial verification bindings."""

    code: str
    canonical_bytes: bytes


def verify_offline_review(
    evidence: object,
) -> OfflineReviewVerification | OfflineReviewFailure:
    """Check caller-supplied offline facts for internal consistency only."""
    try:
        return _verify_offline_review(evidence)
    except Exception:
        return _failure("INPUT_INVALID")


def _verify_offline_review(
    evidence: object,
) -> OfflineReviewVerification | OfflineReviewFailure:
    """Implement verification after containing malformed-object failures."""
    if not _has_exact_unaliased_containers(evidence, set()):
        return _failure("INPUT_INVALID")
    if type(evidence) is not dict or set(evidence) != _EVIDENCE_FIELDS:
        return _failure("INPUT_INVALID")
    if any(not _is_identity(evidence[field]) for field in _BINDING_FIELDS):
        return _failure("INPUT_INVALID")

    observations = evidence["observations"]
    if type(observations) is not list or not observations:
        return _failure("INPUT_INVALID")
    if any(not _is_observation(observation) for observation in observations):
        return _failure("INPUT_INVALID")

    for observation in observations:
        if any(observation[field] != evidence[field] for field in _BINDING_FIELDS):
            return _failure("BINDING_MISMATCH")

    orders = [observation["order"] for observation in observations]
    identities = [observation["observation_identity"] for observation in observations]
    if len(orders) != len(set(orders)) or len(identities) != len(set(identities)):
        return _failure("ORDER_AMBIGUOUS")

    latest = max(observations, key=lambda observation: observation["order"])
    if latest["signature_verified"] is not True:
        return _failure("SIGNATURE_UNVERIFIED")
    if latest["review_state"] != "verified":
        return _failure("REVIEW_NOT_VERIFIED")

    bindings = {
        "status": "VERIFIED_OFFLINE",
        "subject_identity": evidence["subject_identity"],
        "subject_revision": evidence["subject_revision"],
        "baseline_revision": evidence["baseline_revision"],
        "review_identity": evidence["review_identity"],
        "issuer_identity": evidence["issuer_identity"],
        "receipt_digest": evidence["receipt_digest"],
        "evidence_digest": evidence["evidence_digest"],
        "signed_payload_digest": evidence["signed_payload_digest"],
        "signature_result_identity": evidence["signature_result_identity"],
        "signer_identity": evidence["signer_identity"],
        "signer_key_identity": evidence["signer_key_identity"],
        "latest_observation_identity": latest["observation_identity"],
        "latest_order": latest["order"],
    }
    return OfflineReviewVerification(
        status="VERIFIED_OFFLINE",
        subject_identity=evidence["subject_identity"],
        subject_revision=evidence["subject_revision"],
        baseline_revision=evidence["baseline_revision"],
        review_identity=evidence["review_identity"],
        issuer_identity=evidence["issuer_identity"],
        receipt_digest=evidence["receipt_digest"],
        evidence_digest=evidence["evidence_digest"],
        signed_payload_digest=evidence["signed_payload_digest"],
        signature_result_identity=evidence["signature_result_identity"],
        signer_identity=evidence["signer_identity"],
        signer_key_identity=evidence["signer_key_identity"],
        latest_observation_identity=latest["observation_identity"],
        latest_order=latest["order"],
        canonical_bytes=_canonical_bytes(bindings),
    )


def _failure(code: str) -> OfflineReviewFailure:
    """Return one immutable failure with an exact canonical representation."""
    return OfflineReviewFailure(
        code=code,
        canonical_bytes=_canonical_bytes({"code": code}),
    )


def _canonical_bytes(value: dict[str, object]) -> bytes:
    """Return deterministic strict UTF-8 JSON bytes for one result."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8", errors="strict")


def _has_exact_unaliased_containers(value: object, seen: set[int]) -> bool:
    """Reject container subclasses, cycles, and repeated mutable references."""
    if type(value) not in {dict, list}:
        return type(value) in {bool, int, str}
    marker = id(value)
    if marker in seen:
        return False
    seen.add(marker)
    if isinstance(value, list):
        return all(_has_exact_unaliased_containers(item, seen) for item in value)
    if not isinstance(value, dict):
        return False
    return all(
        type(key) is str and _has_exact_unaliased_containers(item, seen)
        for key, item in value.items()
    )


def _is_identity(value: object) -> bool:
    """Return whether a value is one non-empty opaque exact string."""
    return type(value) is str and bool(value)


def _is_observation(value: object) -> bool:
    """Validate one observation without interpreting opaque identities."""
    if type(value) is not dict or set(value) != _OBSERVATION_FIELDS:
        return False
    if any(not _is_identity(value[field]) for field in _BINDING_FIELDS):
        return False
    if not _is_identity(value["observation_identity"]):
        return False
    if type(value["order"]) is not int or value["order"] <= 0:
        return False
    if type(value["review_state"]) is not str:
        return False
    if value["review_state"] not in _REVIEW_STATES:
        return False
    return type(value["signature_verified"]) is bool
