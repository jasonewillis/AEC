"""Deterministic, non-authoritative private mentoring context."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec.contracts import normalize_exact_json
from aec.resolver import PHASES, ResolutionDecision, compute_resolution_hash


LENS_FIELDS = {"cards", "identity", "revision", "schema_version"}
CARD_FIELDS = {
    "guidance",
    "id",
    "phase",
    "principle_ids",
    "questions",
    "source_ids",
}
PRINCIPLE_ID = re.compile(r"^aec-[a-z0-9-]+$")


class PrivateMentorLensError(ValueError):
    """Report invalid local mentoring context without producing a decision."""


@dataclass(frozen=True)
class PrivateMentorCard:
    """One immutable supplemental card selected after authoritative resolution."""

    guidance: tuple[str, ...]
    identity: str
    phase: str
    principle_ids: tuple[str, ...]
    questions: tuple[str, ...]
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON representation of the private card."""
        return {
            "guidance": list(self.guidance),
            "id": self.identity,
            "phase": self.phase,
            "principle_ids": list(self.principle_ids),
            "questions": list(self.questions),
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class PrivateMentorLens:
    """Validated local context that cannot alter an AEC resolution."""

    canonical_bytes: bytes
    cards: tuple[PrivateMentorCard, ...]
    identity: str
    lens_hash: str
    revision: str


@dataclass(frozen=True)
class MentoringEnvelope:
    """An authoritative decision plus optional non-authoritative context."""

    decision: ResolutionDecision
    lens: PrivateMentorLens | None
    selected_cards: tuple[PrivateMentorCard, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a detached mentoring envelope while preserving decision identity."""
        supplemental_context = None
        if self.lens is not None:
            supplemental_context = {
                "cards": [card.to_dict() for card in self.selected_cards],
                "identity": self.lens.identity,
                "lens_hash": self.lens.lens_hash,
                "revision": self.lens.revision,
            }
        return {
            "authoritative_decision": self.decision.to_dict(),
            "authoritative_resolution_hash": self.decision.resolution_hash,
            "executes": False,
            "mutates": False,
            "schema_version": "1.0.0",
            "supplemental_context": supplemental_context,
        }


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object while rejecting ambiguous duplicate names."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PrivateMentorLensError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _canonical_json_bytes(value: object) -> bytes:
    """Return deterministic bytes for a validated private lens."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8", errors="strict")


def _validate_string_list(value: object, field: str) -> tuple[str, ...]:
    """Return one non-empty unique string list or reject it."""
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise PrivateMentorLensError(f"{field} must be a non-empty string list")
    if len(value) != len(set(value)):
        raise PrivateMentorLensError(f"{field} must contain unique values")
    return tuple(value)


def _parse_card(value: object, index: int) -> PrivateMentorCard:
    """Validate and freeze one private mentoring card."""
    if not isinstance(value, dict) or set(value) != CARD_FIELDS:
        raise PrivateMentorLensError(f"cards[{index}] fields do not match the contract")
    identity = value.get("id")
    phase = value.get("phase")
    if not isinstance(identity, str) or not identity.strip():
        raise PrivateMentorLensError(f"cards[{index}].id must be a non-empty string")
    if not isinstance(phase, str) or phase not in PHASES:
        raise PrivateMentorLensError(f"cards[{index}].phase is unsupported")
    principle_ids = _validate_string_list(
        value.get("principle_ids"),
        f"cards[{index}].principle_ids",
    )
    if not all(PRINCIPLE_ID.fullmatch(item) for item in principle_ids):
        raise PrivateMentorLensError(
            f"cards[{index}].principle_ids must use AEC principle identities"
        )
    return PrivateMentorCard(
        guidance=_validate_string_list(
            value.get("guidance"),
            f"cards[{index}].guidance",
        ),
        identity=identity,
        phase=phase,
        principle_ids=principle_ids,
        questions=_validate_string_list(
            value.get("questions"),
            f"cards[{index}].questions",
        ),
        source_ids=_validate_string_list(
            value.get("source_ids"),
            f"cards[{index}].source_ids",
        ),
    )


def load_private_mentor_lens(path: Path | None) -> PrivateMentorLens | None:
    """Load local context, returning no supplement when the file is absent."""
    if path is None:
        return None
    try:
        path.stat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise PrivateMentorLensError(
            f"private mentor lens cannot be inspected: {error}"
        ) from error
    if not path.is_file():
        raise PrivateMentorLensError("private mentor lens path must be a file")
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream, object_pairs_hook=_reject_duplicate_keys)
        value = normalize_exact_json(value)
    except PrivateMentorLensError:
        raise
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise PrivateMentorLensError(f"private mentor lens is invalid: {error}") from error
    if not isinstance(value, dict) or set(value) != LENS_FIELDS:
        raise PrivateMentorLensError("private mentor lens fields do not match the contract")
    if value.get("schema_version") != "1.0.0":
        raise PrivateMentorLensError("private mentor lens schema_version must equal 1.0.0")
    identity = value.get("identity")
    revision = value.get("revision")
    if not isinstance(identity, str) or not identity.strip():
        raise PrivateMentorLensError("private mentor lens identity must be non-empty")
    if not isinstance(revision, str) or not revision.strip():
        raise PrivateMentorLensError("private mentor lens revision must be non-empty")
    raw_cards = value.get("cards")
    if not isinstance(raw_cards, list) or not raw_cards:
        raise PrivateMentorLensError("private mentor lens cards must be a non-empty list")
    cards = tuple(_parse_card(card, index) for index, card in enumerate(raw_cards))
    identities = [card.identity for card in cards]
    if len(identities) != len(set(identities)):
        raise PrivateMentorLensError("private mentor lens card identities must be unique")
    canonical_bytes = _canonical_json_bytes(value)
    lens_hash = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
    return PrivateMentorLens(
        canonical_bytes=canonical_bytes,
        cards=cards,
        identity=identity,
        lens_hash=lens_hash,
        revision=revision,
    )


def apply_private_mentor_lens(
    decision: ResolutionDecision,
    lens: PrivateMentorLens | None,
) -> MentoringEnvelope:
    """Attach matching private context after resolution without changing authority."""
    payload = decision.to_dict()
    if payload.get("resolution_hash") != decision.resolution_hash:
        raise PrivateMentorLensError(
            "embedded authoritative decision hash does not match"
        )
    if compute_resolution_hash(payload) != decision.resolution_hash:
        raise PrivateMentorLensError("authoritative decision hash is invalid")
    if lens is None:
        return MentoringEnvelope(decision=decision, lens=None, selected_cards=())
    phase = payload.get("phase")
    rationale = payload.get("rationale")
    principle_ids = (
        set(rationale.get("principle_ids", []))
        if isinstance(rationale, dict)
        else set()
    )
    selected = tuple(card for card in lens.cards if card.phase == phase)
    for card in selected:
        if principle_ids.isdisjoint(card.principle_ids):
            raise PrivateMentorLensError(
                f"private mentor card {card.identity} does not match the authoritative principle"
            )
    return MentoringEnvelope(decision=decision, lens=lens, selected_cards=selected)
