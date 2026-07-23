#!/usr/bin/env python3
"""Generate the literal-only resolver program artifact."""

from __future__ import annotations

import argparse
import json
import pprint
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRAM_PATH = ROOT / "config" / "resolver" / "resolver-program.json"
SCHEMA_PATH = ROOT / "schemas" / "resolver-program.schema.json"
GENERATED_PATH = ROOT / "aec" / "_generated" / "resolver_program.py"
PROGRAM_FIELDS = {"decision_schema_version", "outcomes", "schema_version"}
PROGRAM_SCHEMA_VERSION = "1.0.0"
DECISION_SCHEMA_VERSION = "4.0.0"
CATALOG_OUTCOMES = {
    "evidence_complete": {
        "allowed": True,
        "gate": "Ready",
        "reason_code": "ACCEPTANCE_EVIDENCE_COMPLETE",
    },
    "evidence_incomplete": {
        "allowed": True,
        "gate": "Evidence needed",
        "reason_code": None,
    },
}
UNAVAILABLE_CONSTANTS = {
    "allowed": False,
    "gate": "Blocked",
    "reason_code": "SKILL_UNAVAILABLE",
}
UNAVAILABLE_STRING_FIELDS = ("anti_example", "rationale_summary")
UNAVAILABLE_STRING_LIST_FIELDS = ("finished", "good", "required_evidence")
UNAVAILABLE_OUTCOME_FIELDS = (
    set(UNAVAILABLE_CONSTANTS)
    | set(UNAVAILABLE_STRING_FIELDS)
    | set(UNAVAILABLE_STRING_LIST_FIELDS)
)
OUTCOME_FIELDS = {
    name: set(outcome) for name, outcome in CATALOG_OUTCOMES.items()
}
OUTCOME_FIELDS["skill_unavailable"] = UNAVAILABLE_OUTCOME_FIELDS


def _is_non_empty_string_list(value: object) -> bool:
    return (
        type(value) is list
        and bool(value)
        and all(type(item) is str and bool(item) for item in value)
    )


def _matches_constant_object(
    value: dict[str, object], expected: dict[str, object]
) -> bool:
    return all(
        type(value[field]) is type(expected_value)
        and value[field] == expected_value
        for field, expected_value in expected.items()
    )


def load_program() -> object:
    """Read the declarative resolver program as strict UTF-8 JSON."""
    with PROGRAM_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate_program(program: object) -> list[str]:
    """Validate the closed resolver program shape before generation."""
    if type(program) is not dict or set(program) != PROGRAM_FIELDS:
        return ["resolver program fields do not match the contract"]
    errors: list[str] = []
    if program["schema_version"] != PROGRAM_SCHEMA_VERSION:
        errors.append("resolver program schema_version must equal 1.0.0")
    if program["decision_schema_version"] != DECISION_SCHEMA_VERSION:
        errors.append("decision_schema_version must equal 4.0.0")
    outcomes = program["outcomes"]
    if type(outcomes) is not dict or set(outcomes) != set(OUTCOME_FIELDS):
        return errors + ["resolver program outcomes do not match the contract"]
    complete = outcomes["evidence_complete"]
    incomplete = outcomes["evidence_incomplete"]
    unavailable = outcomes["skill_unavailable"]
    if type(complete) is not dict or set(complete) != OUTCOME_FIELDS[
        "evidence_complete"
    ]:
        errors.append("evidence_complete fields do not match the contract")
    elif not _matches_constant_object(
        complete, CATALOG_OUTCOMES["evidence_complete"]
    ):
        errors.append("evidence_complete outcome does not match the contract")
    if type(incomplete) is not dict or set(incomplete) != OUTCOME_FIELDS[
        "evidence_incomplete"
    ]:
        errors.append("evidence_incomplete fields do not match the contract")
    elif not _matches_constant_object(
        incomplete, CATALOG_OUTCOMES["evidence_incomplete"]
    ):
        errors.append("evidence_incomplete outcome does not match the contract")
    if type(unavailable) is not dict or set(unavailable) != OUTCOME_FIELDS[
        "skill_unavailable"
    ]:
        errors.append("skill_unavailable fields do not match the contract")
    elif (
        not _matches_constant_object(unavailable, UNAVAILABLE_CONSTANTS)
    ):
        errors.append("skill_unavailable outcome does not match the contract")
    else:
        for field in UNAVAILABLE_STRING_FIELDS:
            if type(unavailable[field]) is not str or not unavailable[field]:
                errors.append(
                    f"skill_unavailable.{field} must be a non-empty string"
                )
        for field in UNAVAILABLE_STRING_LIST_FIELDS:
            if not _is_non_empty_string_list(unavailable[field]):
                errors.append(
                    f"skill_unavailable.{field} must be a non-empty string list"
                )
    return errors


def render_program(program: object) -> str:
    """Render one deterministic Python assignment containing only literals."""
    errors = validate_program(program)
    if errors:
        raise ValueError("; ".join(errors))
    literal = pprint.pformat(program, sort_dicts=True, width=88)
    return f"RESOLVER_PROGRAM = {literal}\n"


def _constant_object_schema(value: dict[str, object]) -> dict[str, object]:
    """Return a closed schema for one exact object value."""
    return {
        "additionalProperties": False,
        "properties": {field: {"const": item} for field, item in value.items()},
        "required": sorted(value),
        "type": "object",
    }


def resolver_program_schema() -> dict[str, object]:
    """Build the public schema from the executable resolver contract."""
    unavailable_properties = {
        field: {"const": value} for field, value in UNAVAILABLE_CONSTANTS.items()
    }
    unavailable_properties.update(
        {
            field: {"minLength": 1, "type": "string"}
            for field in UNAVAILABLE_STRING_FIELDS
        }
    )
    unavailable_properties.update(
        {
            field: {"$ref": "#/$defs/nonEmptyStringList"}
            for field in UNAVAILABLE_STRING_LIST_FIELDS
        }
    )
    unavailable_schema = {
        "additionalProperties": False,
        "properties": unavailable_properties,
        "required": sorted(UNAVAILABLE_OUTCOME_FIELDS),
        "type": "object",
    }
    return {
        "$defs": {
            "nonEmptyStringList": {
                "items": {"minLength": 1, "type": "string"},
                "minItems": 1,
                "type": "array",
            }
        },
        "$id": "https://aec.local/schemas/resolver-program.schema.json",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "additionalProperties": False,
        "properties": {
            "decision_schema_version": {"const": DECISION_SCHEMA_VERSION},
            "outcomes": {
                "additionalProperties": False,
                "properties": {
                    name: _constant_object_schema(value)
                    for name, value in CATALOG_OUTCOMES.items()
                }
                | {"skill_unavailable": unavailable_schema},
                "required": sorted(
                    [*CATALOG_OUTCOMES, "skill_unavailable"]
                ),
                "type": "object",
            },
            "schema_version": {"const": PROGRAM_SCHEMA_VERSION},
        },
        "required": sorted(PROGRAM_FIELDS),
        "title": "AEC deterministic resolver program",
        "type": "object",
    }


def render_schema() -> str:
    """Render the deterministic schema generated from the closed contract."""
    return json.dumps(
        resolver_program_schema(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the generated artifact or check that the checked-in copy is current."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    rendered = render_program(load_program())
    rendered_schema = render_schema()
    if arguments.check:
        if not SCHEMA_PATH.exists():
            print(f"FAIL missing resolver program schema: {SCHEMA_PATH}")
            return 1
        if SCHEMA_PATH.read_text(encoding="utf-8") != rendered_schema:
            print("FAIL resolver program schema is stale")
            return 1
        if not GENERATED_PATH.exists():
            print(f"FAIL missing generated resolver: {GENERATED_PATH}")
            return 1
        if GENERATED_PATH.read_text(encoding="utf-8") != rendered:
            print("FAIL generated resolver program is stale")
            return 1
        print("PASS generated resolver program is current")
        return 0
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(rendered_schema, encoding="utf-8")
    GENERATED_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_PATH.write_text(rendered, encoding="utf-8")
    print(f"WROTE {GENERATED_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
