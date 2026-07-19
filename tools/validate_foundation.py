#!/usr/bin/env python3
"""Validate AEC provenance, course traceability, and resolver decisions."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aec.contracts import validate_project_profile  # noqa: E402, F401
from aec.resolver import compute_resolution_hash, validate_resolution_request  # noqa: E402


HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
HASH_VALUE = re.compile(r"^sha256:[0-9a-f]{64}$")
REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]+$")

GATES = {"Blocked", "Needs review", "Evidence needed", "Ready"}

REQUIRED_RESOLUTION_FIELDS = {
    "allowed",
    "anti_example",
    "available_procedures",
    "capability_profile_version",
    "environment",
    "executes",
    "finished",
    "gate",
    "good",
    "lane",
    "mutates",
    "phase",
    "policy_version",
    "primary_procedure",
    "project_profile_version",
    "rationale",
    "reason_code",
    "required_evidence",
    "required_procedure",
    "resolution_hash",
    "revision",
    "schema_version",
    "source_identities",
    "source_revisions",
    "task_id",
    "workflow",
    "workflow_stage",
}

STAGE_PHASES = {
    "Understand": {"Intake", "Framing"},
    "Design": {"Spec", "Plan"},
    "Execute": {"Build", "Verify"},
    "Assure & Release": {"Review", "PR", "Deploy"},
}
EXPECTED_PHASES = [
    "Intake",
    "Framing",
    "Spec",
    "Plan",
    "Build",
    "Verify",
    "Review",
    "PR",
    "Deploy",
]


def load_json(path: Path) -> Any:
    """Load JSON from a UTF-8 file."""
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate_resolution(resolution: object) -> list[str]:
    """Return fail-closed validation errors for a resolver decision."""
    if not isinstance(resolution, dict):
        return ["resolution must be an object"]

    errors: list[str] = []
    keys = set(resolution)
    missing = sorted(REQUIRED_RESOLUTION_FIELDS - keys)
    unknown = sorted(keys - REQUIRED_RESOLUTION_FIELDS)
    if missing:
        errors.append(f"missing resolution fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"unknown resolution fields: {', '.join(unknown)}")

    if resolution.get("schema_version") != "1.0.0":
        errors.append("schema_version must equal 1.0.0")
    if not isinstance(resolution.get("allowed"), bool):
        errors.append("allowed must be a boolean")
    if resolution.get("executes") is not False:
        errors.append("AEC decisions must set executes=false")
    if resolution.get("mutates") is not False:
        errors.append("AEC decisions must set mutates=false")

    if resolution.get("gate") not in GATES:
        errors.append("gate is unsupported")

    reason_code = resolution.get("reason_code")
    if not isinstance(reason_code, str) or not REASON_CODE.fullmatch(reason_code):
        errors.append("reason_code must be uppercase snake case")

    stage = resolution.get("workflow_stage")
    phase = resolution.get("phase")
    if stage not in STAGE_PHASES:
        errors.append("workflow_stage is unsupported")
    elif phase not in STAGE_PHASES[stage]:
        errors.append("phase does not belong to workflow_stage")

    required_evidence = resolution.get("required_evidence")
    if not isinstance(required_evidence, list) or not all(
        isinstance(item, str) and item for item in required_evidence
    ):
        errors.append("required_evidence must be a list of non-empty strings")

    available_procedures = resolution.get("available_procedures")
    valid_available_procedures = isinstance(available_procedures, list) and all(
        isinstance(item, dict)
        and set(item) == {"identity", "revision"}
        and all(isinstance(value, str) and value for value in item.values())
        for item in available_procedures
    )
    if not valid_available_procedures:
        errors.append("available_procedures must be normalized procedure references")
    elif available_procedures != sorted(
        available_procedures,
        key=lambda item: (item["identity"], item["revision"]),
    ) or len(available_procedures) != len(
        {(item["identity"], item["revision"]) for item in available_procedures}
    ):
        errors.append("available_procedures must be sorted and unique")

    required_procedure = resolution.get("required_procedure")
    valid_required_procedure = (
        isinstance(required_procedure, dict)
        and set(required_procedure) == {"identity", "revision"}
        and all(isinstance(value, str) and value for value in required_procedure.values())
    )
    if not valid_required_procedure:
        errors.append("required_procedure must identify one pinned procedure")

    primary_procedure = resolution.get("primary_procedure")
    unavailable = (
        resolution.get("gate") == "Blocked"
        and resolution.get("reason_code") == "SKILL_UNAVAILABLE"
    )
    if unavailable:
        if resolution.get("allowed") is not False:
            errors.append("SKILL_UNAVAILABLE decisions must set allowed=false")
        if primary_procedure is not None:
            errors.append("unavailable required procedure cannot be selected")
        if isinstance(required_evidence, list) and "procedure-availability" not in required_evidence:
            errors.append("unavailable required procedure needs availability evidence")
    elif not isinstance(primary_procedure, str) or not primary_procedure:
        errors.append("primary_procedure must identify the selected procedure")

    if valid_required_procedure and valid_available_procedures:
        required_reference = (
            required_procedure["identity"],
            required_procedure["revision"],
        )
        available_references = {
            (item["identity"], item["revision"]) for item in available_procedures
        }
        if unavailable and required_reference in available_references:
            errors.append("unavailable required procedure is present in availability facts")
        if not unavailable and required_reference not in available_references:
            errors.append("selected procedure is absent from availability facts")
        if not unavailable and primary_procedure != required_procedure["identity"]:
            errors.append("selected procedure must equal the required procedure")

    for field in ("finished", "good"):
        value = resolution.get(field)
        if not isinstance(value, list) or not value or not all(
            isinstance(item, str) and item for item in value
        ):
            errors.append(f"{field} must be a non-empty list of non-empty strings")

    anti_example = resolution.get("anti_example")
    if not isinstance(anti_example, str) or not anti_example:
        errors.append("anti_example must be a non-empty string")

    rationale = resolution.get("rationale")
    if not isinstance(rationale, dict) or set(rationale) != {"principle_ids", "summary"}:
        errors.append("rationale fields do not match the contract")
    else:
        principle_ids = rationale.get("principle_ids")
        if not isinstance(principle_ids, list) or not principle_ids or not all(
            isinstance(item, str) and item for item in principle_ids
        ):
            errors.append("rationale principle_ids must be a non-empty string list")
        if not isinstance(rationale.get("summary"), str) or not rationale.get("summary"):
            errors.append("rationale summary must be a non-empty string")

    expected_source_keys = {
        "capability_profile",
        "consumer_profile",
        "policy",
        "procedure",
        "workflow",
    }
    source_identities = resolution.get("source_identities")
    if not isinstance(source_identities, dict) or set(source_identities) != expected_source_keys:
        errors.append("source_identities fields do not match the contract")
    elif not all(isinstance(item, str) and item for item in source_identities.values()):
        errors.append("source_identities values must be non-empty strings")

    source_revisions = resolution.get("source_revisions")
    if not isinstance(source_revisions, dict) or set(source_revisions) != expected_source_keys:
        errors.append("source_revisions fields do not match the contract")
    elif not all(isinstance(item, str) and item for item in source_revisions.values()):
        errors.append("source_revisions values must be non-empty strings")

    for field in (
        "capability_profile_version",
        "environment",
        "lane",
        "policy_version",
        "project_profile_version",
        "task_id",
        "workflow",
    ):
        if not isinstance(resolution.get(field), str) or not resolution.get(field):
            errors.append(f"{field} must be a non-empty string")

    revision = resolution.get("revision")
    if not isinstance(revision, str) or not HEX_REVISION.fullmatch(revision):
        errors.append("revision must be a lowercase 40-character Git commit")

    resolution_hash = resolution.get("resolution_hash")
    if not isinstance(resolution_hash, str) or not HASH_VALUE.fullmatch(resolution_hash):
        errors.append("resolution_hash must be sha256 followed by 64 lowercase hex characters")
    elif resolution_hash != compute_resolution_hash(resolution):
        errors.append("resolution_hash does not match canonical payload")

    return errors


def validate_provenance(provenance: object) -> list[str]:
    """Validate pinned upstream relationships and licensing boundaries."""
    if not isinstance(provenance, dict):
        return ["provenance lock must be an object"]
    errors: list[str] = []
    if set(provenance) != {"schema_version", "upstreams"}:
        errors.append("provenance lock fields do not match the contract")
    if provenance.get("schema_version") != "1.0.0":
        errors.append("provenance schema_version must equal 1.0.0")

    upstreams = provenance.get("upstreams")
    if not isinstance(upstreams, list):
        return errors + ["upstreams must be a list"]

    upstream_names = [
        item.get("name")
        for item in upstreams
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    if len(upstream_names) != len(set(upstream_names)):
        errors.append("upstream names must be unique")
    by_name = {
        item.get("name"): item
        for item in upstreams
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if set(by_name) != {"blueprint", "workflows"}:
        errors.append("provenance must define exactly workflows and blueprint")

    workflows = by_name.get("workflows", {})
    if workflows.get("license") != "MIT":
        errors.append("Workflows must retain its verified MIT license")
    if workflows.get("relationship") != "pattern-source":
        errors.append("Workflows relationship must be pattern-source")

    blueprint = by_name.get("blueprint", {})
    if not blueprint.get("license") and blueprint.get("relationship") != "reference-only":
        errors.append("Blueprint must remain reference-only without a verified adoption license")

    for name, upstream in by_name.items():
        if set(upstream) != {"license", "name", "relationship", "repository", "revision"}:
            errors.append(f"{name} fields do not match the upstream contract")
        revision = upstream.get("revision")
        if not isinstance(revision, str) or not HEX_REVISION.fullmatch(revision):
            errors.append(f"{name} revision must be a pinned 40-character Git commit")
        repository = upstream.get("repository")
        if not isinstance(repository, str) or not repository.startswith("https://github.com/"):
            errors.append(f"{name} repository must be an HTTPS GitHub URL")

    return errors


def validate_course_guidance(guidance: object) -> list[str]:
    """Validate complete, uniquely identified course-derived guidance."""
    if not isinstance(guidance, dict):
        return ["course guidance must be an object"]

    errors: list[str] = []
    if set(guidance) != {
        "ai_engineer_lessons",
        "evals_monitoring_lessons",
        "schema_version",
    }:
        errors.append("course guidance fields do not match the contract")
    if guidance.get("schema_version") != "1.0.0":
        errors.append("course guidance schema_version must equal 1.0.0")
    core = guidance.get("ai_engineer_lessons")
    evals = guidance.get("evals_monitoring_lessons")
    if not isinstance(core, list) or len(core) != 13:
        errors.append("AI Engineer coverage must be exactly 13 lessons")
    if not isinstance(evals, list) or len(evals) != 8:
        errors.append("Evals & Monitoring coverage must be exactly 8 lessons")

    core_lessons = core if isinstance(core, list) else []
    eval_lessons = evals if isinstance(evals, list) else []
    lessons = core_lessons + eval_lessons
    identifiers: list[str] = []
    for lesson in lessons:
        if not isinstance(lesson, dict):
            errors.append("every course lesson must be an object")
            continue
        identifier = lesson.get("id")
        if not isinstance(identifier, str) or not identifier:
            errors.append("every course lesson must have a non-empty id")
        else:
            identifiers.append(identifier)
        for field in ("title", "principle"):
            if not isinstance(lesson.get(field), str) or not lesson.get(field):
                errors.append(f"course lesson {identifier or '<unknown>'} needs {field}")
    if len(identifiers) != len(set(identifiers)):
        errors.append("course lesson identifiers must be unique")

    for lesson in core_lessons:
        if not isinstance(lesson, dict):
            continue
        phases = lesson.get("phase")
        if not isinstance(phases, list) or not phases:
            errors.append(f"course lesson {lesson.get('id', '<unknown>')} needs phase coverage")
        elif not all(phase == "All" or phase in EXPECTED_PHASES for phase in phases):
            errors.append(f"course lesson {lesson.get('id', '<unknown>')} has an invalid phase")

    expected_core = {f"ai-engineer-{number:02d}" for number in range(1, 14)}
    expected_evals = {f"evals-monitoring-{number:02d}" for number in range(1, 9)}
    if {item for item in identifiers if item.startswith("ai-engineer-")} != expected_core:
        errors.append("AI Engineer lesson identifiers must cover 01 through 13")
    if {item for item in identifiers if item.startswith("evals-monitoring-")} != expected_evals:
        errors.append("Evals & Monitoring lesson identifiers must cover 01 through 08")

    return errors


def validate_workflow(workflow: object) -> list[str]:
    """Validate the reusable ticket-to-PR lifecycle registry."""
    if not isinstance(workflow, dict):
        return ["workflow must be an object"]

    errors: list[str] = []
    if set(workflow) != {"gate_precedence", "id", "schema_version", "stages"}:
        errors.append("workflow fields do not match the contract")
    if workflow.get("schema_version") != "1.0.0":
        errors.append("workflow schema_version must equal 1.0.0")
    if workflow.get("id") != "ticket-to-pr":
        errors.append("foundation workflow id must equal ticket-to-pr")

    stages = workflow.get("stages")
    if not isinstance(stages, list):
        return errors + ["workflow stages must be a list"]

    actual_phases: list[str] = []
    actual_mapping: dict[str, set[str]] = {}
    for stage in stages:
        if not isinstance(stage, dict):
            errors.append("every workflow stage must be an object")
            continue
        if set(stage) != {"name", "phases"}:
            errors.append("workflow stage fields do not match the contract")
        name = stage.get("name")
        phases = stage.get("phases")
        if not isinstance(name, str) or not isinstance(phases, list):
            errors.append("every workflow stage needs a name and phase list")
            continue
        if not all(isinstance(phase, str) for phase in phases):
            errors.append(f"workflow stage {name} contains a non-string phase")
            continue
        actual_phases.extend(phases)
        actual_mapping[name] = set(phases)

    if actual_phases != EXPECTED_PHASES:
        errors.append("workflow phases must preserve the canonical nine-phase order")
    if actual_mapping != STAGE_PHASES:
        errors.append("workflow stage-to-phase mapping must match the canonical lifecycle")
    if workflow.get("gate_precedence") != [
        "Blocked",
        "Needs review",
        "Evidence needed",
        "Ready",
    ]:
        errors.append("workflow gate precedence must remain fail-closed")
    return errors


def report_errors(label: str, errors: list[str]) -> bool:
    """Print one validation result and return whether it passed."""
    if not errors:
        print(f"PASS {label}")
        return True
    for error in errors:
        print(f"FAIL {label}: {error}")
    return False


def main() -> int:
    """Validate the complete foundation bootstrap contract."""
    checks = [
        report_errors(
            "provenance",
            validate_provenance(load_json(ROOT / "provenance" / "upstream-lock.json")),
        ),
        report_errors(
            "course-guidance",
            validate_course_guidance(load_json(ROOT / "provenance" / "course-guidance.json")),
        ),
        report_errors(
            "workflow.ticket-to-pr",
            validate_workflow(load_json(ROOT / "config" / "workflows" / "ticket-to-pr.json")),
        ),
        report_errors(
            "resolution.valid",
            validate_resolution(load_json(ROOT / "tests" / "fixtures" / "resolution.valid.json")),
        ),
        report_errors(
            "resolution-request.verify",
            validate_resolution_request(
                load_json(
                    ROOT
                    / "tests"
                    / "fixtures"
                    / "resolver"
                    / "golden"
                    / "verify.json"
                )
            ),
        ),
    ]

    wrong_hash = validate_resolution(
        load_json(ROOT / "tests" / "fixtures" / "resolution.wrong-hash.json")
    )
    checks.append(
        report_errors(
            "red-canary.wrong-hash",
            []
            if "resolution_hash does not match canonical payload" in wrong_hash
            else ["canary did not detect the wrong hash"],
        )
    )

    mutating = validate_resolution(
        load_json(ROOT / "tests" / "fixtures" / "resolution.mutating-aec.json")
    )
    required_mutation_errors = {
        "AEC decisions must set executes=false",
        "AEC decisions must set mutates=false",
    }
    checks.append(
        report_errors(
            "red-canary.mutating-aec",
            []
            if required_mutation_errors.issubset(set(mutating))
            else ["canary passed unexpectedly"],
        )
    )
    malformed_request = validate_resolution_request(
        load_json(
            ROOT
            / "tests"
            / "fixtures"
            / "resolver"
            / "red"
            / "malformed-available-procedure.json"
        )
    )
    checks.append(
        report_errors(
            "red-canary.malformed-available-procedure",
            []
            if malformed_request
            == [
                "available_procedures[0] must contain exactly identity and revision"
            ]
            else ["canary did not detect the malformed procedure reference"],
        )
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
