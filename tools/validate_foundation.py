#!/usr/bin/env python3
"""Validate AEC provenance, course traceability, and resolver decisions."""

from __future__ import annotations

import ast
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aec.contracts import validate_project_profile  # noqa: E402, F401
from aec.consumer import (  # noqa: E402
    ConsumerStateRejection,
    resolve_consumer_state,
    validate_consumer_state,
)
from aec.resolver import (  # noqa: E402
    BLOCKER_REASON_REGISTRY,
    compute_resolution_hash,
    validate_procedure_catalog,
    validate_resolution_request,
)
from tools.validate_blueprint_skills import (  # noqa: E402
    EXPECTED_AUTHORIZATION,
    validate_blueprint_installation,
)


HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
HASH_VALUE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
AEC_PRINCIPLE_ID = re.compile(r"^aec-[a-z0-9-]+$")
REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]+$")
SUPPORTED_REASON_CODES = {
    "ACCEPTANCE_EVIDENCE_COMPLETE",
    "ACCEPTANCE_EVIDENCE_INCOMPLETE",
    "SKILL_UNAVAILABLE",
    *BLOCKER_REASON_REGISTRY,
}

GATES = {"Blocked", "Needs review", "Evidence needed", "Ready"}
REVIEW_ATTESTATION_IMPORTS = frozenset(
    {
        ("from", "__future__", ("annotations",)),
        ("from", "dataclasses", ("dataclass",)),
        ("import", "json", ()),
    }
)
REVIEW_ATTESTATION_CALL_NAMES = frozenset(
    {
        "OfflineReviewFailure",
        "OfflineReviewVerification",
        "_canonical_bytes",
        "_failure",
        "_has_exact_unaliased_containers",
        "_is_identity",
        "_is_observation",
        "_verify_offline_review",
        "all",
        "any",
        "bool",
        "dataclass",
        "frozenset",
        "id",
        "isinstance",
        "len",
        "max",
        "set",
        "type",
    }
)
REVIEW_ATTESTATION_CALL_ATTRIBUTES = frozenset(
    {
        "add",
        "dumps",
        "encode",
        "items",
    }
)
REVIEW_ATTESTATION_FORBIDDEN_REFERENCES = frozenset(
    {
        "__import__",
        "__builtins__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "input",
        "open",
    }
)
REVIEW_ATTESTATION_PROTECTED_NAMES = frozenset(
    {
        *REVIEW_ATTESTATION_CALL_NAMES,
        "json",
    }
)
COURSE_EXPRESSIVE_FIELDS = {
    "advice",
    "body",
    "content",
    "description",
    "effect",
    "excerpt",
    "guidance",
    "interpretation",
    "lesson_mapping",
    "notes",
    "operational_effect",
    "phase",
    "policy_mapping",
    "principle",
    "prompt",
    "runtime_prompt",
    "summary",
}
AI_ENGINEER_TITLES = (
    "The Shift To Agentic Engineering",
    "How Coding Agents Work",
    "The Agent Development Workflow",
    "Choose Your Agent",
    "Project Foundations",
    "Agent Skills",
    "Spec-Driven Development",
    "Task Management",
    "Testing Agent Work",
    "Reviewing Agent Work",
    "Deploy With Agents",
    "Scaling Your Impact",
    "BONUS: Agent Loops And Goals",
)
AI_ENGINEER_HASHES = (
    "cedad90972f6dff876b5549964bccaa4f5036d2a3c164eca41fc2d5c01e8bb64",
    "fa9eee23f8396ea6452850c4c7379816128c5aea85321c094aeffac17d31543a",
    "ea3ece74e598476330b758c06bce300d41361c879f52cd0735cc2da7387ad515",
    "3fca81dc82eb2c93125dd259c9b25ce346b0f5e9b87a9c1c62b10fa3667703c6",
    "36cb20c37f4f51f82294de68deacc9aec94ec403e66230da394f49b098a39b47",
    "840fc9fa2a946cad8692ad6309a7cce299031faab3f948c6867d7a997c92eda6",
    "29bcf2e81764aafb02b773791f3550ee0f7a8d3b7058851c43fea73c0848c748",
    "0df87b9138090380163a9379a89498963005700fbc5c75e8f2e296b0907524ec",
    "eaefc642913ee7234b3f99765f54d8cdae76749d9bcbfa6c807a0d689a5d1e05",
    "58bd76df8c2cc7a6dc0cd0232c761a3420f880d16448dc9108b7e610d8048391",
    "ca2d968a390c8682eee559fc86a21a0e7897c3addcbde0a95da5b29257f72ba7",
    "9837b27ce179b6a123b7fe26a0a565e311c65a1e30c3c5201777618ff3921218",
    "9e09e88233d2502b3fd233a11bad47d14ac5bb685b75fca723d64a9dd856a594",
)
EXPECTED_AI_ENGINEER_LESSONS = tuple(
    {
        "id": f"ai-engineer-{index:02d}",
        "sha256": sha256,
        "source_file": f"{index}. {title}.rtf",
        "title": title,
    }
    for index, (title, sha256) in enumerate(
        zip(AI_ENGINEER_TITLES, AI_ENGINEER_HASHES, strict=True),
        start=1,
    )
)
EXPECTED_EVALS_LESSONS = tuple(
    {
        "id": f"evals-monitoring-{index:02d}",
        "sha256": None,
        "source_file": None,
        "title": title,
    }
    for index, title in enumerate(
        (
            "Introduction",
            "Introduction To LangFuse",
            "LangFuse For Pydantic Agents",
            "Introduction To Evals",
            "Unit Tests",
            "Manual Evals",
            "LLM-As-A-Judge",
            "Resources",
        ),
        start=1,
    )
)
EXPECTED_COURSE_SOURCE_SETS = (
    {
        "id": "ai-engineer",
        "lessons": list(EXPECTED_AI_ENGINEER_LESSONS),
        "relationship": "factual-provenance-only",
        "supplemental": [
            {
                "id": "ai-engineer-gateway",
                "sha256": (
                    "9ec5e796ad9ee48e8b46e030f2bbf0cafacc8b7c987950b43bc1acc6c2bd4144"
                ),
                "source_file": "2a. coding-agents-and-the-gateway.md.pdf",
                "title": "Coding Agents And The Gateway",
            }
        ],
        "title": "AI Engineer",
        "visibility": "private",
    },
    {
        "id": "aia-week-5-evals-monitoring",
        "lessons": list(EXPECTED_EVALS_LESSONS),
        "relationship": "factual-provenance-only",
        "supplemental": [],
        "title": "AIA Week 5 Evals & Monitoring",
        "visibility": "private",
    },
)
PRIVATE_COURSE_IDENTITIES = frozenset(
    {
        "ai-engineer",
        "ai-engineer-gateway",
        "aia-week-5-evals-monitoring",
        *(f"ai-engineer-{number:02d}" for number in range(1, 14)),
        *(f"evals-monitoring-{number:02d}" for number in range(1, 9)),
    }
)
COURSE_RUNTIME_IDENTITY = re.compile(
    r"(?<![a-z0-9])(?:"
    + "|".join(
        re.escape(identity)
        for identity in sorted(PRIVATE_COURSE_IDENTITIES, key=len, reverse=True)
    )
    + r")(?![a-z0-9])"
)

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
    "input_bindings",
    "lane",
    "mutates",
    "phase",
    "policy_version",
    "primary_blocker",
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

    if resolution.get("schema_version") != "3.0.0":
        errors.append("schema_version must equal 3.0.0")
    if not isinstance(resolution.get("allowed"), bool):
        errors.append("allowed must be a boolean")
    if resolution.get("executes") is not False:
        errors.append("AEC decisions must set executes=false")
    if resolution.get("mutates") is not False:
        errors.append("AEC decisions must set mutates=false")

    input_bindings = resolution.get("input_bindings")
    if not isinstance(input_bindings, dict) or set(input_bindings) != {
        "procedure_catalog",
        "resolution_request",
    }:
        errors.append("input_bindings fields do not match the contract")
    elif not all(
        isinstance(value, str) and HASH_VALUE.fullmatch(value)
        for value in input_bindings.values()
    ):
        errors.append("input_bindings values must be SHA-256 bindings")

    if resolution.get("gate") not in GATES:
        errors.append("gate is unsupported")

    reason_code = resolution.get("reason_code")
    if not isinstance(reason_code, str) or not REASON_CODE.fullmatch(reason_code):
        errors.append("reason_code must be uppercase snake case")
    elif reason_code not in SUPPORTED_REASON_CODES:
        errors.append("reason_code is unsupported")

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
        and all(
            isinstance(value, str) and value for value in required_procedure.values()
        )
    )
    if not valid_required_procedure:
        errors.append("required_procedure must identify one pinned procedure")

    primary_procedure = resolution.get("primary_procedure")
    primary_blocker = resolution.get("primary_blocker")
    procedure_is_populated = isinstance(primary_procedure, str) and bool(
        primary_procedure
    )
    blocker_is_populated = primary_blocker is not None
    if procedure_is_populated == blocker_is_populated:
        errors.append("decision must contain exactly one primary procedure or blocker")

    valid_primary_blocker = (
        isinstance(primary_blocker, dict)
        and set(primary_blocker) == {"identity", "reason_code"}
        and all(isinstance(value, str) and value for value in primary_blocker.values())
    )
    if primary_blocker is not None and not valid_primary_blocker:
        errors.append(
            "primary_blocker must be null or contain identity and reason_code"
        )
    unavailable = (
        resolution.get("gate") == "Blocked"
        and resolution.get("reason_code") == "SKILL_UNAVAILABLE"
    )
    caller_blocked = (
        resolution.get("gate") == "Blocked"
        and resolution.get("reason_code") in BLOCKER_REASON_REGISTRY
    )
    if unavailable:
        if resolution.get("allowed") is not False:
            errors.append("SKILL_UNAVAILABLE decisions must set allowed=false")
        if primary_procedure is not None:
            errors.append("unavailable required procedure cannot be selected")
        if not valid_primary_blocker:
            errors.append("SKILL_UNAVAILABLE decisions require a primary blocker")
        elif primary_blocker["reason_code"] != "SKILL_UNAVAILABLE":
            errors.append("primary_blocker.reason_code must equal SKILL_UNAVAILABLE")
        if required_evidence != ["procedure-availability"]:
            errors.append(
                "unavailable required procedure needs exactly procedure-availability evidence"
            )
    elif caller_blocked:
        if resolution.get("allowed") is not False:
            errors.append("caller-blocked decisions must set allowed=false")
        if primary_procedure is not None:
            errors.append("caller-blocked decisions cannot select a procedure")
        if not valid_primary_blocker:
            errors.append("caller-blocked decisions require a primary blocker")
        elif primary_blocker["reason_code"] != reason_code:
            errors.append("primary_blocker.reason_code must equal reason_code")
        expected_evidence = BLOCKER_REASON_REGISTRY[reason_code]["required_evidence"]
        if required_evidence != expected_evidence:
            errors.append(
                "caller-blocked decision evidence must match its blocker reason"
            )
    elif not isinstance(primary_procedure, str) or not primary_procedure:
        errors.append("primary_procedure must identify the selected procedure")
    elif primary_blocker is not None:
        errors.append("non-blocked decisions must set primary_blocker=null")

    gate = resolution.get("gate")
    if gate == "Ready":
        if resolution.get("allowed") is not True:
            errors.append("Ready decisions must set allowed=true")
        if reason_code != "ACCEPTANCE_EVIDENCE_COMPLETE":
            errors.append("Ready decisions must use ACCEPTANCE_EVIDENCE_COMPLETE")
        if required_evidence != []:
            errors.append("Ready decisions must not require evidence")
    elif gate == "Evidence needed":
        if resolution.get("allowed") is not True:
            errors.append("Evidence needed decisions must set allowed=true")
        if reason_code != "ACCEPTANCE_EVIDENCE_INCOMPLETE":
            errors.append(
                "Evidence needed decisions must use ACCEPTANCE_EVIDENCE_INCOMPLETE"
            )
        if not isinstance(required_evidence, list) or not required_evidence:
            errors.append("Evidence needed decisions must require evidence")
    elif gate == "Blocked" and not (unavailable or caller_blocked):
        errors.append("Blocked decision reason is unsupported")

    if valid_required_procedure and valid_available_procedures:
        required_reference = (
            required_procedure["identity"],
            required_procedure["revision"],
        )
        available_references = {
            (item["identity"], item["revision"]) for item in available_procedures
        }
        if unavailable and required_reference in available_references:
            errors.append(
                "unavailable required procedure is present in availability facts"
            )
        if (
            not unavailable
            and not caller_blocked
            and required_reference not in available_references
        ):
            errors.append("selected procedure is absent from availability facts")
        if (
            not unavailable
            and not caller_blocked
            and primary_procedure != required_procedure["identity"]
        ):
            errors.append("selected procedure must equal the required procedure")
        if (
            unavailable
            and valid_primary_blocker
            and primary_blocker["identity"] != required_procedure["identity"]
        ):
            errors.append(
                "primary_blocker.identity must equal required_procedure.identity"
            )

    for field in ("finished", "good"):
        value = resolution.get(field)
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(item, str) and item for item in value)
        ):
            errors.append(f"{field} must be a non-empty list of non-empty strings")

    anti_example = resolution.get("anti_example")
    if not isinstance(anti_example, str) or not anti_example:
        errors.append("anti_example must be a non-empty string")

    rationale = resolution.get("rationale")
    if not isinstance(rationale, dict) or set(rationale) != {
        "principle_ids",
        "summary",
    }:
        errors.append("rationale fields do not match the contract")
    else:
        principle_ids = rationale.get("principle_ids")
        if (
            not isinstance(principle_ids, list)
            or not principle_ids
            or not all(isinstance(item, str) and item for item in principle_ids)
        ):
            errors.append("rationale principle_ids must be a non-empty string list")
        if not isinstance(rationale.get("summary"), str) or not rationale.get(
            "summary"
        ):
            errors.append("rationale summary must be a non-empty string")

    expected_source_keys = {
        "capability_profile",
        "consumer_profile",
        "policy",
        "procedure",
        "workflow",
    }
    source_identities = resolution.get("source_identities")
    if (
        not isinstance(source_identities, dict)
        or set(source_identities) != expected_source_keys
    ):
        errors.append("source_identities fields do not match the contract")
    elif not all(isinstance(item, str) and item for item in source_identities.values()):
        errors.append("source_identities values must be non-empty strings")

    source_revisions = resolution.get("source_revisions")
    if (
        not isinstance(source_revisions, dict)
        or set(source_revisions) != expected_source_keys
    ):
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
    if not isinstance(resolution_hash, str) or not HASH_VALUE.fullmatch(
        resolution_hash
    ):
        errors.append(
            "resolution_hash must be sha256 followed by 64 lowercase hex characters"
        )
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
    if blueprint.get("license") is not None:
        errors.append(
            "Blueprint license must remain null unless independently verified"
        )
    if blueprint.get("relationship") != "authorized-skill-source":
        errors.append("Blueprint relationship must be authorized-skill-source")
    if blueprint.get("authorization") != EXPECTED_AUTHORIZATION:
        errors.append("Blueprint authorization record does not match")

    for name, upstream in by_name.items():
        expected_fields = {
            "license",
            "name",
            "relationship",
            "repository",
            "revision",
        }
        if name == "blueprint":
            expected_fields.add("authorization")
        if set(upstream) != expected_fields:
            errors.append(f"{name} fields do not match the upstream contract")
        revision = upstream.get("revision")
        if not isinstance(revision, str) or not HEX_REVISION.fullmatch(revision):
            errors.append(f"{name} revision must be a pinned 40-character Git commit")
        repository = upstream.get("repository")
        if not isinstance(repository, str) or not repository.startswith(
            "https://github.com/"
        ):
            errors.append(f"{name} repository must be an HTTPS GitHub URL")

    return errors


def _nested_keys(value: object) -> set[str]:
    """Return every string key found in nested JSON-compatible data."""
    if isinstance(value, dict):
        return set(value).union(*(_nested_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_nested_keys(item) for item in value))
    return set()


def _nested_strings(value: object) -> list[str]:
    """Return decoded string keys and values from JSON-compatible data."""
    strings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                strings.append(key)
            strings.extend(_nested_strings(item))
    elif isinstance(value, list):
        for item in value:
            strings.extend(_nested_strings(item))
    elif isinstance(value, str):
        strings.append(value)
    return strings


def _render_path(path: Path) -> Path:
    """Render repository paths relatively and external fixtures absolutely."""
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def validate_course_inventory(inventory: object) -> list[str]:
    """Validate factual-only metadata for private course source sets."""
    if not isinstance(inventory, dict):
        return ["course inventory must be an object"]

    errors: list[str] = []
    for field in sorted(_nested_keys(inventory) & COURSE_EXPRESSIVE_FIELDS):
        errors.append(f"course inventory contains forbidden expressive field: {field}")
    if set(inventory) != {"schema_version", "source_sets"}:
        errors.append("course inventory fields do not match the contract")
    if inventory.get("schema_version") != "1.0.0":
        errors.append("course inventory schema_version must equal 1.0.0")
    source_sets = inventory.get("source_sets")
    if not isinstance(source_sets, list):
        return errors + ["course inventory source_sets must be a list"]

    by_id: dict[str, dict[str, Any]] = {}
    lesson_ids: list[str] = []
    for source_set in source_sets:
        if not isinstance(source_set, dict):
            errors.append("every course source set must be an object")
            continue
        if set(source_set) != {
            "id",
            "lessons",
            "relationship",
            "supplemental",
            "title",
            "visibility",
        }:
            errors.append("course source set fields do not match the contract")
        source_id = source_set.get("id")
        if not isinstance(source_id, str) or not source_id:
            errors.append("every course source set must have a non-empty id")
            continue
        if source_id in by_id:
            errors.append("course source set identifiers must be unique")
        by_id[source_id] = source_set
        if source_set.get("visibility") != "private":
            errors.append(f"course source set {source_id} must remain private")
        if source_set.get("relationship") != "factual-provenance-only":
            errors.append(
                f"course source set {source_id} must remain factual-provenance-only"
            )
        if not isinstance(source_set.get("title"), str) or not source_set.get("title"):
            errors.append(f"course source set {source_id} needs a title")

        for collection_name in ("lessons", "supplemental"):
            records = source_set.get(collection_name)
            if not isinstance(records, list):
                errors.append(
                    f"course source set {source_id} {collection_name} must be a list"
                )
                continue
            for record in records:
                if not isinstance(record, dict):
                    errors.append("every course source record must be an object")
                    continue
                if set(record) != {"id", "sha256", "source_file", "title"}:
                    errors.append(
                        "course source record fields do not match the contract"
                    )
                record_id = record.get("id")
                if not isinstance(record_id, str) or not record_id:
                    errors.append("every course source record must have a non-empty id")
                else:
                    lesson_ids.append(record_id)
                if not isinstance(record.get("title"), str) or not record.get("title"):
                    errors.append(
                        f"course source record {record_id or '<unknown>'} needs a title"
                    )
                source_file = record.get("source_file")
                if source_file is not None and (
                    not isinstance(source_file, str) or not source_file
                ):
                    errors.append(
                        "course source record "
                        f"{record_id or '<unknown>'} has an invalid source_file"
                    )
                sha256 = record.get("sha256")
                if sha256 is not None and (
                    not isinstance(sha256, str) or not SHA256_HEX.fullmatch(sha256)
                ):
                    errors.append(
                        f"course source record {record_id or '<unknown>'} has an invalid sha256"
                    )

    if set(by_id) != {"ai-engineer", "aia-week-5-evals-monitoring"}:
        errors.append("course inventory must define the two factual source sets")
    if len(lesson_ids) != len(set(lesson_ids)):
        errors.append("course source record identifiers must be unique")

    ai_engineer = by_id.get("ai-engineer", {})
    ai_lessons = ai_engineer.get("lessons")
    if not isinstance(ai_lessons, list) or len(ai_lessons) != 13:
        errors.append("AI Engineer coverage must be exactly 13 lessons")
    else:
        expected_ids = [f"ai-engineer-{number:02d}" for number in range(1, 14)]
        if [
            record.get("id") for record in ai_lessons if isinstance(record, dict)
        ] != expected_ids:
            errors.append(
                "AI Engineer lesson identifiers must preserve order 01 through 13"
            )
        if not all(
            isinstance(record, dict)
            and isinstance(record.get("sha256"), str)
            and SHA256_HEX.fullmatch(record["sha256"])
            for record in ai_lessons
        ):
            errors.append("every AI Engineer lesson must have an exact SHA-256")
    ai_supplemental = ai_engineer.get("supplemental")
    if not isinstance(ai_supplemental, list) or len(ai_supplemental) != 1:
        errors.append("AI Engineer gateway must be one supplemental source")

    evals = by_id.get("aia-week-5-evals-monitoring", {})
    eval_lessons = evals.get("lessons")
    if not isinstance(eval_lessons, list) or len(eval_lessons) != 8:
        errors.append("Evals & Monitoring coverage must be exactly 8 lessons")
    if source_sets != list(EXPECTED_COURSE_SOURCE_SETS):
        errors.append(
            "course inventory factual manifest must match the verified record"
        )
    return errors


def validate_principle_registry(registry: object) -> list[str]:
    """Validate independently authored AEC principle identities."""
    if not isinstance(registry, dict):
        return ["principle registry must be an object"]
    errors: list[str] = []
    if set(registry) != {"principles", "schema_version"}:
        errors.append("principle registry fields do not match the contract")
    if registry.get("schema_version") != "1.0.0":
        errors.append("principle registry schema_version must equal 1.0.0")
    principles = registry.get("principles")
    if not isinstance(principles, list) or not principles:
        return errors + ["principle registry must contain principles"]
    identities: list[str] = []
    for principle in principles:
        if not isinstance(principle, dict):
            errors.append("every AEC principle must be an object")
            continue
        if set(principle) != {"id", "revision", "statement"}:
            errors.append("AEC principle fields do not match the contract")
        identity = principle.get("id")
        if not isinstance(identity, str) or not AEC_PRINCIPLE_ID.fullmatch(identity):
            errors.append("AEC principle id must match ^aec-[a-z0-9-]+$")
        else:
            identities.append(identity)
            if COURSE_RUNTIME_IDENTITY.search(identity):
                errors.append(
                    "AEC principle id must not embed a private course identity"
                )
        revision = principle.get("revision")
        if not isinstance(revision, str) or not revision:
            errors.append(f"AEC principle {identity or '<unknown>'} needs a revision")
        statement = principle.get("statement")
        if not isinstance(statement, str) or not statement:
            errors.append(f"AEC principle {identity or '<unknown>'} needs a statement")
    if len(identities) != len(set(identities)):
        errors.append("AEC principle identities must be unique")
    return errors


def validate_procedure_principles(catalog: object, registry: object) -> list[str]:
    """Reject procedure authority not owned by the AEC principle registry."""
    errors = validate_principle_registry(registry)
    if errors:
        return errors
    if not isinstance(catalog, dict) or not isinstance(catalog.get("procedures"), list):
        return ["procedure catalog must contain procedures"]
    principles = registry["principles"]
    known_ids = {item["id"] for item in principles if isinstance(item, dict)}
    for procedure in catalog["procedures"]:
        if not isinstance(procedure, dict):
            continue
        procedure_id = procedure.get("identity", "<unknown>")
        rationale = procedure.get("rationale")
        if not isinstance(rationale, dict):
            continue
        principle_ids = rationale.get("principle_ids")
        if not isinstance(principle_ids, list):
            continue
        for principle_id in principle_ids:
            if not isinstance(principle_id, str) or not principle_id.startswith("aec-"):
                errors.append(
                    f"procedure {procedure_id} references non-AEC principle {principle_id}"
                )
            elif principle_id not in known_ids:
                errors.append(
                    f"procedure {procedure_id} references unknown AEC principle {principle_id}"
                )
    return errors


def validate_runtime_authority(paths: list[Path]) -> list[str]:
    """Reject private course identities from mapped runtime authority files."""
    errors: list[str] = []
    for path in sorted(paths):
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            errors.append(f"runtime authority file is not valid JSON: {path}")
            continue
        if any(
            COURSE_RUNTIME_IDENTITY.search(item) for item in _nested_strings(content)
        ):
            rendered_path = _render_path(path)
            errors.append(
                f"runtime authority references private course identity in {rendered_path}"
            )
    return errors


def validate_review_attestation_purity(source: str) -> list[str]:
    """Reject capabilities outside the exact offline-review implementation."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ["review attestation module must parse as Python"]

    imports: set[tuple[str, str, tuple[str, ...]]] = set()
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname is not None:
                    errors.append("review attestation imports must not use aliases")
                imports.add(("import", alias.name, ()))
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0 or node.module is None:
                errors.append("review attestation imports must be absolute")
                continue
            names = tuple(alias.name for alias in node.names)
            if any(alias.asname is not None for alias in node.names):
                errors.append("review attestation imports must not use aliases")
            imports.add(("from", node.module, names))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in REVIEW_ATTESTATION_CALL_NAMES:
                    errors.append(
                        f"review attestation call is not admitted: {node.func.id}"
                    )
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr not in REVIEW_ATTESTATION_CALL_ATTRIBUTES:
                    errors.append(
                        f"review attestation call is not admitted: {node.func.attr}"
                    )
            else:
                errors.append("review attestation dynamic call target is not admitted")
        elif (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in REVIEW_ATTESTATION_FORBIDDEN_REFERENCES
        ):
            errors.append(
                f"review attestation forbidden capability is referenced: {node.id}"
            )
        elif (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and node.id in REVIEW_ATTESTATION_PROTECTED_NAMES
        ):
            errors.append(f"review attestation admitted name is rebound: {node.id}")
        elif isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(
            node.ctx, (ast.Store, ast.Del)
        ):
            errors.append("review attestation indirect mutation is not admitted")
        elif isinstance(node, ast.Attribute) and node.attr == "__dict__":
            errors.append("review attestation __dict__ capability is not admitted")
    if imports != REVIEW_ATTESTATION_IMPORTS:
        errors.append("review attestation imports do not match the exact allowlist")
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
        errors.append(
            "workflow stage-to-phase mapping must match the canonical lifecycle"
        )
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


def materialize_consumer_state_case(
    state: dict[str, Any], case: dict[str, Any]
) -> dict[str, Any]:
    """Apply one bounded red-fixture operation to a consumer state record."""
    value = copy.deepcopy(state)
    path = case["path"]
    target: dict[str, Any] = value
    for part in path[:-1]:
        target = target[part]
    if case["operation"] == "remove":
        del target[path[-1]]
    elif case["operation"] == "replace":
        target[path[-1]] = case["value"]
    return value


def main() -> int:
    """Validate the complete foundation bootstrap contract."""
    course_inventory = load_json(ROOT / "provenance" / "course-inventory.json")
    procedure_catalog = load_json(ROOT / "config" / "procedures" / "ticket-to-pr.json")
    consumer_state = load_json(
        ROOT / "tests" / "fixtures" / "consumer-state" / "valid.json"
    )
    principle_registry = load_json(
        ROOT / "config" / "principles" / "aec-engineering.json"
    )
    runtime_authority_paths = sorted((ROOT / "config").rglob("*.json"))
    golden_requests = sorted(
        (ROOT / "tests" / "fixtures" / "resolver" / "golden").glob("*.json")
    )
    checks = [
        report_errors(
            "blueprint-skills",
            validate_blueprint_installation(ROOT),
        ),
        report_errors(
            "provenance",
            validate_provenance(load_json(ROOT / "provenance" / "upstream-lock.json")),
        ),
        report_errors(
            "course-inventory",
            validate_course_inventory(course_inventory),
        ),
        report_errors(
            "principle-registry",
            validate_principle_registry(principle_registry),
        ),
        report_errors(
            "procedure-principles.ticket-to-pr",
            validate_procedure_principles(procedure_catalog, principle_registry),
        ),
        report_errors(
            "runtime-authority.course-boundary",
            validate_runtime_authority(runtime_authority_paths),
        ),
        report_errors(
            "review-attestation.purity",
            validate_review_attestation_purity(
                (ROOT / "aec" / "review_attestation.py").read_text(
                    encoding="utf-8",
                    errors="strict",
                )
            ),
        ),
        report_errors(
            "workflow.ticket-to-pr",
            validate_workflow(
                load_json(ROOT / "config" / "workflows" / "ticket-to-pr.json")
            ),
        ),
        report_errors(
            "procedure-catalog.ticket-to-pr",
            validate_procedure_catalog(procedure_catalog),
        ),
        report_errors(
            "consumer-state.valid",
            validate_consumer_state(consumer_state),
        ),
        report_errors(
            "resolution.valid",
            validate_resolution(
                load_json(ROOT / "tests" / "fixtures" / "resolution.valid.json")
            ),
        ),
    ]
    checks.extend(
        report_errors(
            f"resolution-request.{request_path.stem}",
            validate_resolution_request(load_json(request_path)),
        )
        for request_path in golden_requests
    )

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
            == ["available_procedures[0] must contain exactly identity and revision"]
            else ["canary did not detect the malformed procedure reference"],
        )
    )
    malformed_catalog = validate_procedure_catalog(
        load_json(
            ROOT
            / "tests"
            / "fixtures"
            / "resolver"
            / "red"
            / "malformed-procedure-catalog.json"
        )
    )
    checks.append(
        report_errors(
            "red-canary.malformed-procedure-catalog",
            []
            if malformed_catalog == ["procedures[0] fields do not match the contract"]
            else ["canary did not detect the malformed procedure catalog"],
        )
    )
    unsupported_reason_catalog = load_json(
        ROOT / "config" / "procedures" / "ticket-to-pr.json"
    )
    unsupported_reason_catalog["procedures"][0]["reason_code"] = "ARBITRARY_GREEN"
    unsupported_reason_errors = validate_procedure_catalog(unsupported_reason_catalog)
    checks.append(
        report_errors(
            "red-canary.unsupported-catalog-reason",
            []
            if unsupported_reason_errors
            == [("procedures[0].reason_code must equal ACCEPTANCE_EVIDENCE_INCOMPLETE")]
            else ["canary did not detect the unsupported catalog reason code"],
        )
    )
    tampered_decision = load_json(ROOT / "tests" / "fixtures" / "resolution.valid.json")
    tampered_decision["gate"] = "Ready"
    tampered_decision["resolution_hash"] = compute_resolution_hash(tampered_decision)
    semantic_errors = validate_resolution(tampered_decision)
    required_semantic_errors = {
        "Ready decisions must use ACCEPTANCE_EVIDENCE_COMPLETE",
        "Ready decisions must not require evidence",
    }
    checks.append(
        report_errors(
            "red-canary.semantic-decision-tamper",
            []
            if required_semantic_errors.issubset(set(semantic_errors))
            else ["canary did not detect the semantically tampered decision"],
        )
    )
    expressive_inventory = validate_course_inventory(
        load_json(
            ROOT
            / "tests"
            / "fixtures"
            / "course-boundary"
            / "course-inventory-expressive.json"
        )
    )
    checks.append(
        report_errors(
            "red-canary.course-expressive-content",
            []
            if "course inventory contains forbidden expressive field: principle"
            in expressive_inventory
            else ["canary did not detect expressive course content"],
        )
    )
    runtime_course_identity = validate_runtime_authority(
        [
            ROOT
            / "tests"
            / "fixtures"
            / "course-boundary"
            / "runtime-authority-course-id.json"
        ]
    )
    checks.append(
        report_errors(
            "red-canary.course-runtime-authority",
            []
            if runtime_course_identity
            else ["canary did not detect course runtime authority"],
        )
    )
    consumer_cases = load_json(
        ROOT / "tests" / "fixtures" / "consumer-state" / "red-cases.json"
    )["cases"]
    for case in consumer_cases:
        result = resolve_consumer_state(
            materialize_consumer_state_case(consumer_state, case),
            procedure_catalog,
            current_time=case.get("current_time", "2026-01-01T00:30:00Z"),
            expected_environment=case.get("expected_environment", "test"),
            expected_revision=case.get(
                "expected_revision",
                "0123456789abcdef0123456789abcdef01234567",
            ),
        )
        checks.append(
            report_errors(
                f"red-canary.consumer-state.{case['name']}",
                []
                if isinstance(result, ConsumerStateRejection)
                and result.code == case["code"]
                and result.to_dict()["card"] is None
                else ["consumer-state canary did not fail closed"],
            )
        )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
