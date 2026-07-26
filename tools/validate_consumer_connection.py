#!/usr/bin/env python3
"""Consumer-visible compatibility signal for a pinned AEC checkout.

A contract-tightening pin bump can pass an unrelated routine probe while
breaking a material-decision consumer. `d35f535` (AEC #48) is the concrete
case: it tightened `decision_context` to require `context` and
`schema_version`, and added `confidence`, `expected_result`, and
`principal_uncertainty` to `recommendation`. A consumer pinned to the
previous shape only discovered the break when its own test suite went red,
because a routine connection check never exercises `decision_context`.

This tool is the connection proof a consumer runs against a pinned AEC
*before* attempting any real coaching:

    python3.12 -m tools.validate_consumer_connection

It resolves two built-in probes through the same pure adapter every
consumer uses (`aec.consumer.resolve_consumer_state`):

  * ROUTINE  -- no `decision_context`. Exercises the baseline contract.
  * MATERIAL -- a closed `decision_context` with two choices and one
    recommendation. Exercises the contract this incident broke.

Both probes must resolve to a non-authoritative card (`executes=false`,
`mutates=false`) for the connection to report PASS. Each probe also asserts
its own `decision_support` shape: ROUTINE must render `decision_support: null`
and MATERIAL must render it populated, so a fixture in the wrong slot -- for
example a routine fixture handed to `--material` -- fails instead of passing
by coincidence. A rejection is reported before any card is rendered, and --
for `decision_context` specifically -- is expanded field-by-field against the
current contract's known shape (`decision_context` itself, `context`,
`authority`, every `choices[i]` and its `tradeoffs`, `recommendation`, and
`recommendation.expected_result`) so the failure names exactly what a
consumer must add, remove, or change. A generic "validation failed" is never
sufficient; see `diagnose_decision_context`.

`--self-check` additionally resolves `tests/fixtures/consumer-connection/
previous-contract.json`, a fixture pinned to the pre-#48 `decision_context`
shape, and asserts it is rejected with actionable field-level guidance. That
proves the negative path -- not just the positive one -- stays wired.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec.consumer import ConsumerCard, ConsumerStateRejection, resolve_consumer_state
from aec.mentoring import (
    AUTHORITY_FIELDS,
    CHOICE_FIELDS,
    CONTEXT_FIELDS,
    DECISION_CONTEXT_FIELDS,
    DECISION_CONTEXT_SCHEMA_VERSION,
    EXPECTED_RESULT_FIELDS,
    RECOMMENDATION_FIELDS,
    TRADEOFF_FIELDS,
)


TOOL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = TOOL_ROOT / "config/procedures/ticket-to-pr.json"
FIXTURES = TOOL_ROOT / "tests/fixtures/consumer-connection"
DEFAULT_ROUTINE_PROBE = FIXTURES / "routine.json"
DEFAULT_MATERIAL_PROBE = FIXTURES / "material.json"
PREVIOUS_CONTRACT_FIXTURE = FIXTURES / "previous-contract.json"

# The probes and the previous-contract fixture all pin the same fixed clock
# and identity so the fixtures stay self-contained and independent of the
# real wall clock. They validate contract shape, not freshness.
PROBE_CURRENT_TIME = "2026-01-01T00:30:00Z"
PROBE_ENVIRONMENT = "test"
PROBE_REVISION = "0123456789abcdef0123456789abcdef01234567"


class ConnectionFailure(RuntimeError):
    """A fail-closed compatibility result carrying an actionable message."""


def load_json(path: Path, label: str) -> Any:
    """Load one JSON document or raise a stable connection failure."""
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConnectionFailure(f"{label} is unreadable: {error}") from error


def _diff_fields(actual: dict[str, Any], expected: set[str]) -> tuple[list[str], list[str]]:
    """Return the fields missing from, and unexpected in, one closed object."""
    keys = set(actual)
    return sorted(expected - keys), sorted(keys - expected)


@dataclass(frozen=True)
class DecisionContextDiagnosis:
    """Structured, machine-checkable field-level diagnosis of one decision_context.

    `messages` is the human-readable report. `missing_fields` is the flat set of
    unqualified field names this diagnosis found absent from a required object
    (`decision_context` itself, `context`, `authority`, one `choices[i]`, one
    `tradeoffs`, `recommendation`, or `recommendation.expected_result`). It exists
    so a caller can assert on exact field names instead of testing substrings
    against `messages` -- a substring test against these messages is unsound,
    because every message here starts with the literal `"decision_context"`,
    which itself contains the substring `"context"`.
    """

    messages: tuple[str, ...]
    missing_fields: frozenset[str]

    def __bool__(self) -> bool:
        return bool(self.messages)


def diagnose_decision_context(value: object) -> DecisionContextDiagnosis:
    """Name the exact `decision_context` fields a consumer must add or change.

    Runs independently of `aec.consumer`'s own validator, which short-circuits
    to one generic "fields do not match the contract" message the instant the
    top-level field set disagrees. This walks `context`, `authority`, every
    `choices[i]` and its `tradeoffs`, `recommendation`, and
    `recommendation.expected_result` regardless, so a consumer pinned to a
    stale contract sees every field it is missing in one pass instead of
    fixing one field, rerunning, and discovering the next.
    """
    if value is None:
        return DecisionContextDiagnosis((), frozenset())
    if type(value) is not dict:
        return DecisionContextDiagnosis(("decision_context must be an object",), frozenset())

    findings: list[str] = []
    missing_fields: set[str] = set()
    missing, extra = _diff_fields(value, DECISION_CONTEXT_FIELDS)
    if missing:
        findings.append(
            "decision_context is missing required fields: " + ", ".join(missing)
        )
        missing_fields.update(missing)
    if extra:
        findings.append(
            "decision_context has fields the current contract does not accept: "
            + ", ".join(extra)
        )
    if "schema_version" not in missing and value.get("schema_version") != (
        DECISION_CONTEXT_SCHEMA_VERSION
    ):
        findings.append(
            "decision_context.schema_version must equal "
            f"{DECISION_CONTEXT_SCHEMA_VERSION!r}, found {value.get('schema_version')!r}"
        )

    if "context" not in missing:
        context = value.get("context")
        if type(context) is not dict:
            findings.append("decision_context.context must be an object")
        else:
            context_missing, context_extra = _diff_fields(context, CONTEXT_FIELDS)
            if context_missing:
                findings.append(
                    "decision_context.context is missing required fields: "
                    + ", ".join(context_missing)
                )
                missing_fields.update(context_missing)
            if context_extra:
                findings.append(
                    "decision_context.context has fields the current contract does "
                    "not accept: " + ", ".join(context_extra)
                )

    if "authority" not in missing:
        authority = value.get("authority")
        if type(authority) is not dict:
            findings.append("decision_context.authority must be an object")
        else:
            authority_missing, authority_extra = _diff_fields(authority, AUTHORITY_FIELDS)
            if authority_missing:
                findings.append(
                    "decision_context.authority is missing required fields: "
                    + ", ".join(authority_missing)
                )
                missing_fields.update(authority_missing)
            if authority_extra:
                findings.append(
                    "decision_context.authority has fields the current contract does "
                    "not accept: " + ", ".join(authority_extra)
                )

    if "choices" not in missing:
        choices = value.get("choices")
        if type(choices) is not list:
            findings.append("decision_context.choices must be a list")
        else:
            for index, choice in enumerate(choices):
                field = f"decision_context.choices[{index}]"
                if type(choice) is not dict:
                    findings.append(f"{field} must be an object")
                    continue
                choice_missing, choice_extra = _diff_fields(choice, CHOICE_FIELDS)
                if choice_missing:
                    findings.append(
                        f"{field} is missing required fields: " + ", ".join(choice_missing)
                    )
                    missing_fields.update(choice_missing)
                if choice_extra:
                    findings.append(
                        f"{field} has fields the current contract does not accept: "
                        + ", ".join(choice_extra)
                    )
                if "tradeoffs" not in choice_missing:
                    tradeoffs = choice.get("tradeoffs")
                    if type(tradeoffs) is not dict:
                        findings.append(f"{field}.tradeoffs must be an object")
                    else:
                        tradeoffs_missing, tradeoffs_extra = _diff_fields(
                            tradeoffs, TRADEOFF_FIELDS
                        )
                        if tradeoffs_missing:
                            findings.append(
                                f"{field}.tradeoffs is missing required fields: "
                                + ", ".join(tradeoffs_missing)
                            )
                            missing_fields.update(tradeoffs_missing)
                        if tradeoffs_extra:
                            findings.append(
                                f"{field}.tradeoffs has fields the current contract "
                                "does not accept: " + ", ".join(tradeoffs_extra)
                            )

    recommendation = value.get("recommendation")
    if type(recommendation) is dict:
        rec_missing, rec_extra = _diff_fields(recommendation, RECOMMENDATION_FIELDS)
        if rec_missing:
            findings.append(
                "decision_context.recommendation is missing required fields: "
                + ", ".join(rec_missing)
            )
            missing_fields.update(rec_missing)
        if rec_extra:
            findings.append(
                "decision_context.recommendation has fields the current contract "
                "does not accept: " + ", ".join(rec_extra)
            )
        if "expected_result" not in rec_missing:
            expected_result = recommendation.get("expected_result")
            if type(expected_result) is not dict:
                findings.append(
                    "decision_context.recommendation.expected_result must be an object"
                )
            else:
                result_missing, result_extra = _diff_fields(
                    expected_result, EXPECTED_RESULT_FIELDS
                )
                if result_missing:
                    findings.append(
                        "decision_context.recommendation.expected_result is missing "
                        "required fields: " + ", ".join(result_missing)
                    )
                    missing_fields.update(result_missing)
                if result_extra:
                    findings.append(
                        "decision_context.recommendation.expected_result has fields "
                        "the current contract does not accept: " + ", ".join(result_extra)
                    )
    elif recommendation is not None:
        findings.append("decision_context.recommendation must be an object")

    return DecisionContextDiagnosis(tuple(findings), frozenset(missing_fields))


def resolve_probe(
    state: dict[str, Any],
    catalog: object,
) -> ConsumerCard | ConsumerStateRejection:
    """Resolve one probe through the same pure adapter every consumer uses."""
    return resolve_consumer_state(
        state,
        catalog,
        current_time=PROBE_CURRENT_TIME,
        expected_environment=PROBE_ENVIRONMENT,
        expected_revision=PROBE_REVISION,
    )


def run_probe(
    name: str,
    path: Path,
    catalog: object,
    *,
    expect_decision_support: bool,
) -> dict[str, Any]:
    """Resolve one named probe and return its receipt, or raise on rejection.

    `expect_decision_support` is the contract this probe exists to enforce: a
    ROUTINE probe must resolve with `decision_support: null` and a MATERIAL
    probe must resolve with `decision_support` populated. Without this check
    the proof only confirms the state was accepted, not that it exercised the
    material-decision path it claims to -- a fixture with the wrong shape in
    the wrong slot (a routine fixture handed to `--material`, or vice versa)
    would silently report PASS.
    """
    state = load_json(path, f"{name} probe")
    if type(state) is not dict:
        raise ConnectionFailure(f"{name} probe must contain a JSON object")
    result = resolve_probe(state, catalog)
    if isinstance(result, ConsumerStateRejection):
        rejection = result.to_dict()
        messages = list(rejection["errors"])
        messages.extend(diagnose_decision_context(state.get("decision_context")).messages)
        raise ConnectionFailure(
            f"{name} probe rejected ({rejection['code']}): " + "; ".join(messages)
        )
    card = result.to_dict()
    if card.get("transition_request", {}).get("executes") is not False or (
        card.get("transition_request", {}).get("mutates") is not False
    ):
        raise ConnectionFailure(f"{name} probe resolved to an effectful decision")
    has_decision_support = card.get("decision_support") is not None
    if has_decision_support != expect_decision_support:
        raise ConnectionFailure(
            f"{name} probe decision_support mismatch: expected "
            f"{'present' if expect_decision_support else 'absent'}, found "
            f"{'present' if has_decision_support else 'absent'}. This probe did "
            "not exercise the contract it claims to; check the fixture in this slot."
        )
    return {
        "probe": name,
        "gate": card["gate"],
        "has_decision_support": has_decision_support,
        "status": "PASS",
    }


def validate_connection(
    routine_path: Path,
    material_path: Path,
    catalog_path: Path,
) -> dict[str, Any]:
    """Resolve the ROUTINE and MATERIAL probes and return one PASS receipt."""
    catalog = load_json(catalog_path, "procedure catalog")
    routine = run_probe(
        "routine", routine_path, catalog, expect_decision_support=False
    )
    material = run_probe(
        "material", material_path, catalog, expect_decision_support=True
    )
    return {"probes": [routine, material], "status": "PASS"}


# The previous-contract fixture is missing exactly these five fields under the
# pre-#48 decision_context shape: `context` and `schema_version` at the top
# level, and `confidence`, `expected_result`, and `principal_uncertainty` from
# `recommendation`. self_check asserts this set exactly, structurally, so a
# diagnosis that silently stops reporting one of them fails self-check instead
# of passing by coincidence.
PREVIOUS_CONTRACT_EXPECTED_MISSING_FIELDS = frozenset(
    {"context", "schema_version", "confidence", "expected_result", "principal_uncertainty"}
)


def _verify_previous_contract_diagnosis(diagnosis: DecisionContextDiagnosis) -> None:
    """Assert one diagnosis names exactly the fields the pre-#48 shape lacks.

    Matches on `diagnosis.missing_fields`, a set of exact field names, never on
    substrings of `diagnosis.messages`. Every message here starts with the
    literal `"decision_context"`, which itself contains the substring
    `"context"`, so a substring test against messages can never fail on that
    field and is not a real assertion.
    """
    if not diagnosis.messages:
        raise ConnectionFailure(
            "self-check failed: no actionable decision_context findings were produced"
        )
    if diagnosis.missing_fields != PREVIOUS_CONTRACT_EXPECTED_MISSING_FIELDS:
        raise ConnectionFailure(
            "self-check failed: expected missing_fields "
            f"{sorted(PREVIOUS_CONTRACT_EXPECTED_MISSING_FIELDS)}, got "
            f"{sorted(diagnosis.missing_fields)}"
        )


def self_check(catalog_path: Path) -> None:
    """Prove the negative path stays wired: a previous-contract fixture must fail.

    Loads `tests/fixtures/consumer-connection/previous-contract.json`, which
    reproduces the pre-#48 `decision_context` shape, and asserts it is
    rejected before a card is rendered and that the rejection names exactly
    the specific fields a consumer must add or change.
    """
    catalog = load_json(catalog_path, "procedure catalog")
    state = load_json(PREVIOUS_CONTRACT_FIXTURE, "previous-contract fixture")
    if type(state) is not dict:
        raise ConnectionFailure("previous-contract fixture must contain a JSON object")
    result = resolve_probe(state, catalog)
    if not isinstance(result, ConsumerStateRejection):
        raise ConnectionFailure(
            "self-check failed: the previous-contract fixture must be rejected, "
            "not resolved to a card"
        )
    diagnosis = diagnose_decision_context(state.get("decision_context"))
    _verify_previous_contract_diagnosis(diagnosis)


def parse_arguments() -> argparse.Namespace:
    """Parse connection-proof CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routine", type=Path, default=DEFAULT_ROUTINE_PROBE)
    parser.add_argument("--material", type=Path, default=DEFAULT_MATERIAL_PROBE)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="also prove the previous-contract fixture is rejected with actionable fields",
    )
    return parser.parse_args()


def main() -> int:
    """Run the fail-closed consumer connection proof."""
    arguments = parse_arguments()
    try:
        receipt = validate_connection(
            arguments.routine, arguments.material, arguments.catalog
        )
        if arguments.self_check:
            self_check(arguments.catalog)
    except ConnectionFailure as error:
        print(f"AEC connection: FAIL: {error}")
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
