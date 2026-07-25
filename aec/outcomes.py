"""Local-only outcome receipts binding one AEC decision to its observed result."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from aec.contracts import normalize_exact_json


OUTCOME_RECEIPT_SCHEMA_VERSION = "1.0.0"
OUTCOME_REPORT_SCHEMA_VERSION = "1.0.0"
RECEIPT_FIELDS = {
    "coaching",
    "decision",
    "observed_result",
    "schema_version",
    "verdict",
    "verification",
}
DECISION_FIELDS = {"resolution_hash", "revision", "selected_choice"}
OBSERVED_RESULT_FIELDS = {"direction", "expectation", "measure"}
COACHING_FIELDS = {"burden", "transfer"}
VERIFICATION_FIELDS = {"accepted", "kind", "revision"}
RECORD_FIELDS = {"card", "receipt"}
BURDENS = ("high", "low", "moderate")
TRANSFERS = ("full", "none", "partial")
VERDICTS = (
    "harmful",
    "inconclusive",
    "partially-supported",
    "supported",
    "unsupported",
)
# Every declared expectation maps to exactly one recommendation verdict.
EXPECTATION_VERDICTS = {
    "met": "supported",
    "missed": "unsupported",
    "partially-met": "partially-supported",
    "reversed": "harmful",
    "unobserved": "inconclusive",
}
RESULT_DIRECTIONS = {"decrease", "hold", "increase"}
# Whether an expectation requires the observed direction to match the expected
# one. A missed or unobserved result constrains no direction.
DIRECTION_AGREEMENT = {"met": True, "partially-met": True, "reversed": False}
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
RESOLUTION_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
SLUG_IDENTITY = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
# Field names that would carry content an outcome receipt must never hold.
PROHIBITED_FIELDS = frozenset(
    {
        "author",
        "body",
        "code",
        "commit",
        "commit_message",
        "completion",
        "content",
        "credential",
        "description",
        "diff",
        "email",
        "environment",
        "evidence",
        "file",
        "filename",
        "health",
        "identity",
        "issue",
        "issue_title",
        "log",
        "message",
        "model",
        "model_output",
        "name",
        "notes",
        "output",
        "owner",
        "password",
        "patch",
        "path",
        "person",
        "project",
        "prompt",
        "reason",
        "repository",
        "response",
        "secret",
        "source",
        "summary",
        "text",
        "title",
        "token",
        "url",
        "user",
    }
)
PRIVATE_PATH_PATTERNS = (
    re.compile(r"file://", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])~[/\\]"),
    re.compile(r"(?<![A-Za-z0-9_/])/(?!/)[^\s]+"),
    re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[/\\]"),
    re.compile(r"(?<![\\])\\\\[^\\\s]+\\[^\\\s]+"),
    re.compile(r"(?<![A-Za-z0-9_.])\.{1,2}[/\\]"),
)


@dataclass(frozen=True, slots=True)
class OutcomeReceiptVerification:
    """One receipt whose declared verdict matches its own bound facts."""

    verdict: str
    resolution_hash: str
    revision: str
    selected_choice: str
    canonical_bytes: bytes


@dataclass(frozen=True, slots=True)
class OutcomeReceiptRejection:
    """One fail-closed receipt result that reports no verdict."""

    code: str
    errors: tuple[str, ...]
    canonical_bytes: bytes


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    """Return deterministic strict UTF-8 JSON bytes for one result."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8", errors="strict")


def _rejection(code: str, *errors: str) -> OutcomeReceiptRejection:
    """Build one immutable rejection with no partial verdict."""
    return OutcomeReceiptRejection(
        code=code,
        errors=errors,
        canonical_bytes=_canonical_bytes({"code": code, "errors": list(errors)}),
    )


def _nested_field_names(value: object) -> set[str]:
    """Return every object field name nested in one JSON value."""
    if type(value) is dict:
        return set(value).union(
            *(_nested_field_names(item) for item in value.values()),
            set(),
        )
    if type(value) is list:
        return set().union(*(_nested_field_names(item) for item in value), set())
    return set()


def _nested_strings(value: object) -> list[str]:
    """Return every nested exact string value."""
    if type(value) is dict:
        return [item for nested in value.values() for item in _nested_strings(nested)]
    if type(value) is list:
        return [item for nested in value for item in _nested_strings(nested)]
    return [value] if type(value) is str else []


def _slug(value: object) -> bool:
    """Return whether a value is one lowercase hyphenated identity."""
    return type(value) is str and bool(SLUG_IDENTITY.fullmatch(value))


def _validate_receipt_shape(receipt: dict[str, Any]) -> list[str]:
    """Validate the closed receipt shape without interpreting the card."""
    errors: list[str] = []
    if receipt.get("schema_version") != OUTCOME_RECEIPT_SCHEMA_VERSION:
        errors.append(
            f"schema_version must equal {OUTCOME_RECEIPT_SCHEMA_VERSION}"
        )
    if receipt.get("verdict") not in VERDICTS:
        errors.append("verdict is unsupported")

    decision = receipt.get("decision")
    if type(decision) is not dict or set(decision) != DECISION_FIELDS:
        errors.append("decision fields do not match the contract")
    else:
        resolution_hash = decision.get("resolution_hash")
        if type(resolution_hash) is not str or not RESOLUTION_HASH.fullmatch(
            resolution_hash
        ):
            errors.append("decision.resolution_hash must be a SHA-256 binding")
        revision = decision.get("revision")
        if type(revision) is not str or not HEX_REVISION.fullmatch(revision):
            errors.append(
                "decision.revision must be a lowercase 40-character Git commit"
            )
        if not _slug(decision.get("selected_choice")):
            errors.append("decision.selected_choice must be a declared choice identity")

    observed = receipt.get("observed_result")
    if type(observed) is not dict or set(observed) != OBSERVED_RESULT_FIELDS:
        errors.append("observed_result fields do not match the contract")
    else:
        if not _slug(observed.get("measure")):
            errors.append("observed_result.measure must be a measure identity")
        if observed.get("direction") not in RESULT_DIRECTIONS:
            errors.append("observed_result.direction is unsupported")
        if observed.get("expectation") not in EXPECTATION_VERDICTS:
            errors.append("observed_result.expectation is unsupported")

    coaching = receipt.get("coaching")
    if type(coaching) is not dict or set(coaching) != COACHING_FIELDS:
        errors.append("coaching fields do not match the contract")
    else:
        if coaching.get("burden") not in BURDENS:
            errors.append("coaching.burden is unsupported")
        if coaching.get("transfer") not in TRANSFERS:
            errors.append("coaching.transfer is unsupported")

    verification = receipt.get("verification")
    if type(verification) is not list or not verification:
        errors.append("verification must contain at least one fact")
    else:
        facts: list[tuple[str, str]] = []
        for index, fact in enumerate(verification):
            field = f"verification[{index}]"
            if type(fact) is not dict or set(fact) != VERIFICATION_FIELDS:
                errors.append(f"{field} fields do not match the contract")
                continue
            if type(fact.get("accepted")) is not bool:
                errors.append(f"{field}.accepted must be a boolean")
            if not _slug(fact.get("kind")):
                errors.append(f"{field}.kind must be a verification kind identity")
            revision = fact.get("revision")
            if type(revision) is not str or not HEX_REVISION.fullmatch(revision):
                errors.append(
                    f"{field}.revision must be a lowercase 40-character Git commit"
                )
            else:
                facts.append((str(fact.get("kind")), revision))
        if len(facts) != len(set(facts)):
            errors.append("verification must contain unique facts")
    return errors


def _card_decision(card: object) -> tuple[dict[str, Any], list[str]] | None:
    """Return the decision facts a receipt may bind, or None when absent."""
    if type(card) is not dict:
        return None
    resolution_hash = card.get("resolution_hash")
    transition = card.get("transition_request")
    support = card.get("decision_support")
    if (
        type(resolution_hash) is not str
        or type(transition) is not dict
        or type(transition.get("revision")) is not str
        or type(support) is not dict
    ):
        return None
    choices = support.get("choices")
    recommendation = support.get("recommendation")
    if type(choices) is not list or type(recommendation) is not dict:
        return None
    expected = recommendation.get("expected_result")
    if type(expected) is not dict:
        return None
    identities = [
        choice.get("identity") for choice in choices if type(choice) is dict
    ]
    return (
        {
            "expected_direction": expected.get("direction"),
            "expected_measure": expected.get("measure"),
            "resolution_hash": resolution_hash,
            "revision": transition["revision"],
        },
        [identity for identity in identities if type(identity) is str],
    )


def _derived_verdict(receipt: dict[str, Any]) -> str:
    """Derive the only verdict the receipt's own facts support."""
    revision = receipt["decision"]["revision"]
    current = [
        fact
        for fact in receipt["verification"]
        if fact["accepted"] is True and fact["revision"] == revision
    ]
    if not current:
        return "inconclusive"
    return EXPECTATION_VERDICTS[receipt["observed_result"]["expectation"]]


def verify_outcome_receipt(
    receipt: object,
    card: object,
) -> OutcomeReceiptVerification | OutcomeReceiptRejection:
    """Verify one local outcome receipt against the exact decision it cites."""
    try:
        normalized = normalize_exact_json(receipt)
    except (TypeError, ValueError):
        return _rejection(
            "OUTCOME_RECEIPT_INVALID",
            "outcome receipt must contain only exact JSON values",
        )
    prohibited = sorted(_nested_field_names(normalized) & PROHIBITED_FIELDS)
    if prohibited:
        return _rejection(
            "OUTCOME_RECEIPT_PROHIBITED_FIELD",
            f"outcome receipt must not contain: {', '.join(prohibited)}",
        )
    if any(
        pattern.search(item)
        for item in _nested_strings(normalized)
        for pattern in PRIVATE_PATH_PATTERNS
    ):
        return _rejection(
            "OUTCOME_RECEIPT_PRIVATE_PATH",
            "outcome receipt must not contain private filesystem paths",
        )
    if type(normalized) is not dict or set(normalized) != RECEIPT_FIELDS:
        return _rejection(
            "OUTCOME_RECEIPT_INVALID",
            "outcome receipt fields do not match the contract",
        )
    shape_errors = _validate_receipt_shape(normalized)
    if shape_errors:
        return OutcomeReceiptRejection(
            code="OUTCOME_RECEIPT_INVALID",
            errors=tuple(shape_errors),
            canonical_bytes=_canonical_bytes(
                {"code": "OUTCOME_RECEIPT_INVALID", "errors": shape_errors}
            ),
        )

    decision = _card_decision(card)
    if decision is None:
        return _rejection(
            "OUTCOME_RECEIPT_NO_DECISION",
            "an outcome receipt requires one rendered material decision",
        )
    facts, identities = decision
    bound = normalized["decision"]
    if (
        bound["resolution_hash"] != facts["resolution_hash"]
        or bound["revision"] != facts["revision"]
    ):
        return _rejection(
            "OUTCOME_RECEIPT_DECISION_MISMATCH",
            "outcome receipt does not bind the exact rendered decision",
        )
    if bound["selected_choice"] not in identities:
        return _rejection(
            "OUTCOME_RECEIPT_CHOICE_UNDECLARED",
            "outcome receipt must select one declared choice",
        )
    observed = normalized["observed_result"]
    agrees = observed["direction"] == facts["expected_direction"]
    required = DIRECTION_AGREEMENT.get(observed["expectation"], agrees)
    if observed["measure"] != facts["expected_measure"] or agrees is not required:
        return _rejection(
            "OUTCOME_RECEIPT_RESULT_MISMATCH",
            "observed result does not answer the expected measurable result",
        )
    derived = _derived_verdict(normalized)
    if normalized["verdict"] != derived:
        return _rejection(
            "OUTCOME_RECEIPT_VERDICT_CONTRADICTED",
            f"declared verdict is contradicted by the receipt facts: {derived}",
        )
    bindings = {
        "resolution_hash": bound["resolution_hash"],
        "revision": bound["revision"],
        "selected_choice": bound["selected_choice"],
        "verdict": derived,
    }
    return OutcomeReceiptVerification(
        verdict=derived,
        resolution_hash=bound["resolution_hash"],
        revision=bound["revision"],
        selected_choice=bound["selected_choice"],
        canonical_bytes=_canonical_bytes(bindings),
    )


def evaluate_outcomes(records: object) -> dict[str, Any]:
    """Count coaching value and project impact across verified receipts only."""
    if type(records) is not list:
        raise ValueError("outcome records must be a list")
    normalized: list[dict[str, Any]] = []
    for record in records:
        if type(record) is not dict or set(record) != RECORD_FIELDS:
            raise ValueError("outcome record fields do not match the contract")
        normalized.append(record)

    burden = dict.fromkeys(BURDENS, 0)
    transfer = dict.fromkeys(TRANSFERS, 0)
    verdicts = dict.fromkeys(VERDICTS, 0)
    rejected: list[dict[str, Any]] = []
    verified = 0
    for index, record in enumerate(normalized):
        result = verify_outcome_receipt(record["receipt"], record["card"])
        if isinstance(result, OutcomeReceiptRejection):
            rejected.append({"code": result.code, "index": index})
            continue
        verified += 1
        verdicts[result.verdict] += 1
        coaching = record["receipt"]["coaching"]
        burden[coaching["burden"]] += 1
        transfer[coaching["transfer"]] += 1
    return {
        "authoritative": False,
        "causal_claim": False,
        "coaching_value": {"burden": burden, "transfer": transfer},
        "project_impact": {"verdict": verdicts},
        "rejected": rejected,
        "schema_version": OUTCOME_REPORT_SCHEMA_VERSION,
        "verified": verified,
    }
