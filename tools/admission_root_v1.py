"""Dormant base-owned admission validator over raw Git tree and blob data."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, NamedTuple


ADMISSION_PROTOCOL = "aec-admission-v1"
BEHAVIOR_IDENTITY = (
    "sha256:7f6e614afb78df29d2b1eceb1040b9b0c924ece261de90572dbda03bc8620fa3"
)
ARTIFACT_MANIFEST_ROOT = (
    "sha256:686ece3d31618e22961acd8fe2d8e72d35ae30e750bf86d4efcaa9ad5b3890ef"
)
TRUST_ROOT_LOCK_IDENTITY = (
    "sha256:ce099d7a3d32e6dbc2b788c6aa950fad09b61b49f8b08048ed33cf86806d1c84"
)
REGULAR_MODE = "100644"
OUTCOMES = (
    "BOOTSTRAP-001 BASE_AUTHORITY",
    "ADMISSION-001 EXACT_BASELINE",
    "ADMISSION-002 NO_PRE_ADMISSION_EXECUTION",
)


class ArtifactBaseline(NamedTuple):
    """One admitted artifact path identity."""

    closed_class: str
    sha256: str


class FileBaseline(NamedTuple):
    """One admitted proof-closure path identity."""

    mode: str
    sha256: str


SOURCE_BASELINE: dict[str, str] = {
    "aec/__init__.py": "6eb9af014892dc51902c32b0e1fcac89836e194831f023a5e341d636a1e78173",
    "aec/_generated/__init__.py": (
        "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b"
    ),
    "aec/_generated/resolver_program.py": (
        "4cf7aa4c831abe910d88bb23bf344beaa6dcfa11d0317e63048bb4a05508c270"
    ),
    "aec/contracts.py": "077f7225b232d04ab02e5d908b5af0fb9243ed20def359ac739baefd1ddbedc1",
    "aec/mentoring.py": (
        "06590eec08ef9210b9dd2488d30bd1b6e1e4a2df1fed997fa4b7c0077bd40331"
    ),
    "aec/review_attestation.py": (
        "6e30442e278f855dc3d267e7e4e0412b6abef2805d8b91691b626e96878828db"
    ),
    "aec/resolver.py": (
        "5a0b9701eaa8621adca55ac23c92394ec30b026bf6161da9f822e0abfb3cdb14"
    ),
}
ARTIFACT_BASELINE: dict[str, ArtifactBaseline] = {
    "config/principles/aec-engineering.json": ArtifactBaseline(
        "configuration",
        "730cf21a28ece2ec7389ac7ada1188358d9a02544cc360bb752f7f9c65a11e5f",
    ),
    "config/procedures/ticket-to-pr.json": ArtifactBaseline(
        "configuration",
        "5725ee4a2f905770602950059e9afa2835cf4da648225eff487117555ea8a777",
    ),
    "config/resolver/resolver-program.json": ArtifactBaseline(
        "configuration",
        "da560799943cc99b9bfa68c0ba531f26a815065e7d1b1632a67bc9249f6f97e9",
    ),
    "config/workflows/ticket-to-pr.json": ArtifactBaseline(
        "configuration",
        "6c8a24bde4fb4f0d4c919ce8d7ae3f30b5d6187c6578cd218c300fe1e51c9569",
    ),
    "provenance/blueprint-skills.json": ArtifactBaseline(
        "provenance",
        "a5c23ba937a00aee0e01fe77669dde0cbce72892b8287d0541a4ee3f730f198f",
    ),
    "provenance/course-inventory.json": ArtifactBaseline(
        "provenance",
        "22c775840cbbaca8c9ed77dde00ba1517326c7ab16392f909afe6bbac889d834",
    ),
    "provenance/upstream-lock.json": ArtifactBaseline(
        "provenance",
        "b432bab429f3025351bcd2bae8a4450263ea00951efbb0b20d563b865b19364b",
    ),
    "schemas/consumer-state.schema.json": ArtifactBaseline(
        "schema",
        "12ff738f9b4cb0fefcfebfbf91ceafe0f28631fda415f1c162bcd2d02a2e3f5d",
    ),
    "schemas/course-inventory.schema.json": ArtifactBaseline(
        "schema",
        "3f7dd4afa33cd2fd29089582b20b8fbf2dd6329296bbf96471f9f11ebbd4f45b",
    ),
    "schemas/principle-registry.schema.json": ArtifactBaseline(
        "schema",
        "c300d600856010f82cc2312a8689d45a175ea7f008ce0039b0bfd733707741b5",
    ),
    "schemas/private-mentor-lens.schema.json": ArtifactBaseline(
        "schema",
        "64bc1deef531e7fd00a76fa38a403dbbfe4b6df57ca86fee1c8c9d668560d0fa",
    ),
    "schemas/procedure-catalog.schema.json": ArtifactBaseline(
        "schema",
        "e8652016c71607f68f3b6db09a9994d994a13b568f1a09721c4c2b3b8dcdf027",
    ),
    "schemas/resolution-decision.schema.json": ArtifactBaseline(
        "schema",
        "2a81aeaab10e3722c005895f95573f69b7b07c01f0a58931e3e372d5dc46f679",
    ),
    "schemas/resolution-rejection.schema.json": ArtifactBaseline(
        "schema",
        "abec6e2d28fb25c2f261f0b43224987a3491423bcec5c476eee8537b3a380ece",
    ),
    "schemas/resolution-request.schema.json": ArtifactBaseline(
        "schema",
        "28c54ac54fa8c4dd782e881e7f49d0ecfda8a97aeed15fc07886c34a259c1247",
    ),
    "schemas/resolver-program.schema.json": ArtifactBaseline(
        "schema",
        "ec1bd9ba3ee66e11d6aba7c6b3ecb6367b122df756fd13092ea070a92f9944fb",
    ),
    "skills-lock.json": ArtifactBaseline(
        "skill-lock",
        "077eae10654ada27885194ffd3ef4c238168a1a9a8b4bc8f84cbdf7a3b63746b",
    ),
    "tests/fixtures/consumer-state/red-cases.json": ArtifactBaseline(
        "test-fixture",
        "74ca60bf0080dbc35c610eb18f2f981d140574529694ebfbc2241de2c82ea29e",
    ),
    "tests/fixtures/consumer-state/valid.json": ArtifactBaseline(
        "test-fixture",
        "3d09721fd1a453c9c89a154b82bf31fd2ef8e34a664e6bdc847c02c526290afa",
    ),
    "tests/fixtures/course-boundary/course-inventory-expressive.json": ArtifactBaseline(
        "test-fixture",
        "4a8bb764e0ef1c93168515ca10ab8fcb121bac839dcca6baef2b80bab26a73ce",
    ),
    "tests/fixtures/course-boundary/runtime-authority-course-id.json": ArtifactBaseline(
        "test-fixture",
        "75446a2b3b50921f975e6e35ac1783bb039785808f065e575c7927ebd8d2be9f",
    ),
    "tests/fixtures/private-mentor-lens/valid.json": ArtifactBaseline(
        "test-fixture",
        "1c38ed99df6239cd269f0cab32d4a3f393e6c57f0b32f366a9da5c8a79d002cb",
    ),
    "tests/fixtures/resolution.mutating-aec.json": ArtifactBaseline(
        "test-fixture",
        "cbb97de814da1f70da025fa08860c5f7cc021033de8734c6c4617d41c35953f7",
    ),
    "tests/fixtures/resolution.valid.json": ArtifactBaseline(
        "test-fixture",
        "96789f3fd42b90f943845a0f0c36b7fa4d2815e3da371d89e7b86d57ab95600b",
    ),
    "tests/fixtures/resolution.wrong-hash.json": ArtifactBaseline(
        "test-fixture",
        "e4513e12685b394b6130c4610b054b3d84e056fa843e97a557f516b310bfc84b",
    ),
    "tests/fixtures/resolver/golden/build.json": ArtifactBaseline(
        "test-fixture",
        "98d2818184f161f45749f45efcb4ac88af4bf382ecd66c60f4330e80e536a533",
    ),
    "tests/fixtures/resolver/golden/deploy.json": ArtifactBaseline(
        "test-fixture",
        "7d47893f5a131096bec8696f8cae6ad8bbb16b5a5902373980539b2afa5776ba",
    ),
    "tests/fixtures/resolver/golden/framing.json": ArtifactBaseline(
        "test-fixture",
        "cb319d2973e756f769397105fea5cf3a7d8d8a4f3681da52166106d6314ea7b6",
    ),
    "tests/fixtures/resolver/golden/intake.json": ArtifactBaseline(
        "test-fixture",
        "37f5f62ab17d8a58461934293050e5ffd3393d6388364168a712dcac0a2c772f",
    ),
    "tests/fixtures/resolver/golden/plan.json": ArtifactBaseline(
        "test-fixture",
        "ccfcc7c9d4bd99827ee52a3ce5b9f99cd2c9efdffad71e54ef8ccf38756c7afb",
    ),
    "tests/fixtures/resolver/golden/pr.json": ArtifactBaseline(
        "test-fixture",
        "4c6fddf3f53525158a2a80d3eacb7f9bc392f3f56f00b089cdb2e08829646e3d",
    ),
    "tests/fixtures/resolver/golden/review.json": ArtifactBaseline(
        "test-fixture",
        "b2e9c6eb168bc14df172ffa00707fc69b34de34df96e54e6ed2a295f4859b7ec",
    ),
    "tests/fixtures/resolver/golden/spec.json": ArtifactBaseline(
        "test-fixture",
        "afbe8d1d9a806d669ad30206ebcb0328022c5f77b79f9f4987373f85cfe00686",
    ),
    "tests/fixtures/resolver/golden/verify.json": ArtifactBaseline(
        "test-fixture",
        "ec92d009129b7e93f2f41ea9e826815e03c941d86a981280520eb5e3031156f0",
    ),
    "tests/fixtures/resolver/red/malformed-available-procedure.json": ArtifactBaseline(
        "test-fixture",
        "438c86e6320743fe33b7af09710291a8ff46092bc797cab1e42306c445935e37",
    ),
    "tests/fixtures/resolver/red/malformed-procedure-catalog.json": ArtifactBaseline(
        "test-fixture",
        "97cc0519e22d73b16a714c54c2283774ab196b14a7414bb2d38bbd22d8382450",
    ),
    "tests/fixtures/resolver/red/unavailable-skill.json": ArtifactBaseline(
        "test-fixture",
        "8931bd287eb29dd439a1e657a586c3d0b395bd778d765fbf3ab1a41a00b00c33",
    ),
}
WORKFLOW_TRANSITION_BASELINE: dict[str, str] = {
    ".github/workflows/candidate-admission.yml": (
        "2d0229163087c649042e0f4af0060ab269af036c84df398745f8cb7802ac9068"
    ),
    ".github/workflows/foundation-gate.yml": (
        "75d940adee48523e8c4163cc78b2cb16cc2f8d80317a026677f4b52adb70459b"
    ),
}
WORKFLOW_TRANSITION_BUNDLES: dict[str, str] = {
    ".github/workflows/candidate-admission.yml": (
        ".github/workflows/candidate-admission.yml"
    ),
    ".github/workflows/foundation-gate.yml": (
        ".github/admission/v1/foundation-gate.yml"
    ),
}
PROOF_CLOSURE_BASELINE: dict[str, FileBaseline] = {
    ".claude/skills/milestone": FileBaseline(
        "120000",
        "179787e57e206baeb8719792db0ef2b0ed38bba71ac395db51e83cf02b98724c",
    ),
    ".github/admission/v1/foundation-gate.yml": FileBaseline(
        REGULAR_MODE,
        "75d940adee48523e8c4163cc78b2cb16cc2f8d80317a026677f4b52adb70459b",
    ),
    "aec/consumer.py": FileBaseline(
        REGULAR_MODE,
        "39d5ac572f140e2d45f9c0304b4bf5f4a5315159a7e6243a06b07e3fd79e635a",
    ),
    "tests/test_foundation_behavior.py": FileBaseline(
        REGULAR_MODE,
        "25f544e69b7b66ca768c3a0272ea8448c58f50ae880fa860c1bac828e7533519",
    ),
    "tests/test_review_attestation.py": FileBaseline(
        REGULAR_MODE,
        "033c5f835c55ea4bffb7dd3700d6b562f42efaa329f4f74f24860f1ff18c06c6",
    ),
    "tools/__init__.py": FileBaseline(
        REGULAR_MODE,
        "24fcc84ad8324d8ab9da5493c183e7ae307a1508cdbc4dc2efde04f18ba18811",
    ),
    "tools/generate_resolver.py": FileBaseline(
        REGULAR_MODE,
        "d2fa950f2572fb213eade309f5763739fea1fff4d1f859bb5b85d22cfcf68676",
    ),
    "tools/prove_foundation_behavior.py": FileBaseline(
        REGULAR_MODE,
        "a53aab66774a61e1982229c04c954be36f7cc705a9ee76783b22bfe6148a9291",
    ),
    "tools/validate_blueprint_skills.py": FileBaseline(
        REGULAR_MODE,
        "951d722c12a33903b119fff9ed11c3c6563e09a6f786d348fbab451b1daee77f",
    ),
    "tools/validate_foundation.py": FileBaseline(
        REGULAR_MODE,
        "e9e29cd5a22068e4239c7d1febb4d5355e2a1ae46770df0d6ab4f129e202b5e0",
    ),
}
PYTHON_PATHS = frozenset(
    {
        *SOURCE_BASELINE,
        "aec/adapters.py",
        "aec/consumer.py",
        "aec/mentor.py",
        "aec/mentoring.py",
        "tests/test_admission_root_v1.py",
        "tests/test_agent_adapters.py",
        "tests/test_authority_v2_hostile_corpus.py",
        "tests/test_blueprint_skills.py",
        "tests/test_consumer_interface.py",
        "tests/test_exact_json.py",
        "tests/test_foundation_validation.py",
        "tests/test_foundation_behavior.py",
        "tests/test_private_mentor_lens.py",
        "tests/test_resolver.py",
        "tests/test_resolver_blocker_precedence.py",
        "tests/test_resolver_program.py",
        "tests/test_review_attestation.py",
        "tools/__init__.py",
        "tools/admission_root_v1.py",
        "tools/generate_resolver.py",
        "tools/prove_agent_adapter_parity.py",
        "tools/prove_foundation_behavior.py",
        "tools/prove_private_mentor_lens.py",
        "tools/validate_blueprint_skills.py",
        "tools/validate_foundation.py",
    }
)
VALIDATOR_PATH = "tools/admission_root_v1.py"
ACTIVE_WORKFLOW_PATH = ".github/workflows/candidate-admission.yml"


@dataclass(frozen=True)
class BaseAuthority:
    """Identity of validator and workflow bytes extracted from one base SHA."""

    base_sha: str
    validator_blob_oid: str
    validator_sha256: str
    workflow_blob_oid: str
    workflow_sha256: str


@dataclass(frozen=True)
class GitRecord:
    """One raw NUL-delimited Git stage or tree record."""

    mode: str
    object_id: str
    path: bytes


@dataclass(frozen=True)
class AdmissionReport:
    """Immutable dormant admission verdict."""

    base_authority: BaseAuthority
    behavior_identity: str
    findings: tuple[str, ...]
    passed: bool
    protocol: str = ADMISSION_PROTOCOL


def _hex(value: str, lengths: set[int]) -> bool:
    """Return whether value is lowercase hexadecimal at an allowed length."""
    return len(value) in lengths and all(char in "0123456789abcdef" for char in value)


def git_blob_oid(content: bytes, length: int = 40) -> str:
    """Return the Git blob object ID for SHA-1 or SHA-256 repositories."""
    payload = f"blob {len(content)}\0".encode() + content
    if length == 40:
        return hashlib.sha1(payload).hexdigest()
    if length == 64:
        return hashlib.sha256(payload).hexdigest()
    raise ValueError("Git object ID length is unsupported")


def parse_git_records(raw: bytes, record_format: str) -> tuple[GitRecord, ...]:
    """Parse strict NUL-delimited raw paths without C-quoting or decoding."""
    if not raw or not raw.endswith(b"\0"):
        raise ValueError("Git records must be non-empty and NUL terminated")
    records: list[GitRecord] = []
    seen: set[bytes] = set()
    for encoded in raw[:-1].split(b"\0"):
        if not encoded or encoded.count(b"\t") != 1:
            raise ValueError("Git record delimiter is invalid")
        metadata, path = encoded.split(b"\t", 1)
        if not path or path in seen:
            raise ValueError("Git record paths must be non-empty and unique")
        try:
            fields = metadata.decode("ascii", errors="strict").split(" ")
            path.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError("Git record metadata and paths must be UTF-8") from error
        if record_format == "stage-v1":
            if len(fields) != 3 or fields[2] != "0":
                raise ValueError("Git stage record is invalid")
            mode, object_id = fields[:2]
        elif record_format == "tree-v1":
            if len(fields) != 3 or fields[1] != "blob":
                raise ValueError("Git tree record is invalid")
            mode, object_id = fields[0], fields[2]
        else:
            raise ValueError("Git record format is unsupported")
        if not _hex(object_id, {40, 64}) or mode not in {
            "100644",
            "100755",
            "120000",
            "160000",
        }:
            raise ValueError("Git mode or object ID is invalid")
        seen.add(path)
        records.append(GitRecord(mode, object_id, path))
    return tuple(records)


def artifact_manifest_root(
    baseline: Mapping[str, ArtifactBaseline],
) -> str:
    """Bind sorted artifact path, class, and byte hash rows."""
    rows = [
        [path, baseline[path].closed_class, baseline[path].sha256]
        for path in sorted(baseline)
    ]
    payload = json.dumps(rows, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _authority_valid(authority: BaseAuthority) -> bool:
    """Validate explicit immutable-base authority identities."""
    return (
        _hex(authority.base_sha, {40, 64})
        and _hex(authority.validator_blob_oid, {40, 64})
        and _hex(authority.workflow_blob_oid, {40, 64})
        and _hex(authority.validator_sha256, {64})
        and _hex(authority.workflow_sha256, {64})
    )


def validate_candidate(
    *,
    raw_records: bytes,
    record_format: str,
    blobs: Mapping[str, bytes],
    authority: BaseAuthority,
) -> AdmissionReport:
    """Admit candidate Git data without importing or executing candidate code."""
    findings: set[str] = set()
    if not _authority_valid(authority):
        findings.add("BOOTSTRAP-001 BASE_AUTHORITY")
    try:
        records = parse_git_records(raw_records, record_format)
    except ValueError:
        records = ()
        findings.add("ADMISSION-001 EXACT_BASELINE")
    by_path = {record.path: record for record in records}
    expected_sources = {
        path.encode(): digest for path, digest in SOURCE_BASELINE.items()
    }
    expected_artifacts = {
        path.encode(): artifact.sha256 for path, artifact in ARTIFACT_BASELINE.items()
    }
    expected_closure = {
        path.encode(): baseline for path, baseline in PROOF_CLOSURE_BASELINE.items()
    }
    tracked_python = {
        path.decode()
        for path in by_path
        if path.endswith(b".py")
        and (b"/" not in path or path.startswith((b"aec/", b"tests/", b"tools/")))
    }
    if tracked_python != PYTHON_PATHS:
        findings.add("ADMISSION-001 EXACT_BASELINE")
    tracked_json = {path for path in by_path if path.endswith(b".json")}
    if tracked_json != set(expected_artifacts):
        findings.add("ADMISSION-001 EXACT_BASELINE")
    expected_workflows = {
        path.encode(): digest for path, digest in WORKFLOW_TRANSITION_BASELINE.items()
    }
    tracked_workflows = {
        path
        for path in by_path
        if path.startswith(b".github/workflows/")
        and (path.endswith(b".yml") or path.endswith(b".yaml"))
    }
    if tracked_workflows != set(expected_workflows):
        findings.add("ADMISSION-001 EXACT_BASELINE")
    expected = (
        expected_sources
        | expected_artifacts
        | expected_workflows
        | {path: baseline.sha256 for path, baseline in expected_closure.items()}
    )
    if not set(expected).issubset(by_path):
        findings.add("ADMISSION-001 EXACT_BASELINE")
    for path, digest in expected.items():
        record = by_path.get(path)
        expected_mode = expected_closure.get(
            path, FileBaseline(REGULAR_MODE, digest)
        ).mode
        if record is None or record.mode != expected_mode:
            findings.add("ADMISSION-001 EXACT_BASELINE")
            continue
        content = blobs.get(record.object_id)
        if content is None:
            findings.add("ADMISSION-001 EXACT_BASELINE")
            continue
        if git_blob_oid(content, len(record.object_id)) != record.object_id:
            findings.add("ADMISSION-001 EXACT_BASELINE")
            continue
        if hashlib.sha256(content).hexdigest() != digest:
            findings.add("ADMISSION-001 EXACT_BASELINE")
    validator_record = by_path.get(VALIDATOR_PATH.encode())
    validator_content = (
        None if validator_record is None else blobs.get(validator_record.object_id)
    )
    if (
        validator_record is None
        or validator_record.mode != REGULAR_MODE
        or validator_record.object_id != authority.validator_blob_oid
        or validator_content is None
        or git_blob_oid(validator_content, len(validator_record.object_id))
        != validator_record.object_id
        or hashlib.sha256(validator_content).hexdigest() != authority.validator_sha256
    ):
        findings.add("ADMISSION-001 EXACT_BASELINE")
    workflow_record = by_path.get(ACTIVE_WORKFLOW_PATH.encode())
    if (
        workflow_record is None
        or workflow_record.object_id != authority.workflow_blob_oid
        or authority.workflow_sha256
        != WORKFLOW_TRANSITION_BASELINE[ACTIVE_WORKFLOW_PATH]
    ):
        findings.add("ADMISSION-001 EXACT_BASELINE")
    if artifact_manifest_root(ARTIFACT_BASELINE) != ARTIFACT_MANIFEST_ROOT:
        findings.add("ADMISSION-001 EXACT_BASELINE")
    ordered = tuple(outcome for outcome in OUTCOMES if outcome in findings)
    return AdmissionReport(
        base_authority=authority,
        behavior_identity=BEHAVIOR_IDENTITY,
        findings=ordered,
        passed=not ordered,
    )


def self_check(root: Path) -> tuple[str, ...]:
    """Verify current base bytes against the installed dormant trust root."""
    findings: list[str] = []
    for path, digest in SOURCE_BASELINE.items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != digest:
            findings.append(path)
    for path, artifact in ARTIFACT_BASELINE.items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != artifact.sha256:
            findings.append(path)
    for path, baseline in PROOF_CLOSURE_BASELINE.items():
        candidate = root / path
        content = (
            candidate.readlink().as_posix().encode()
            if baseline.mode == "120000"
            else candidate.read_bytes()
        )
        if hashlib.sha256(content).hexdigest() != baseline.sha256:
            findings.append(path)
    for target, bundle in WORKFLOW_TRANSITION_BUNDLES.items():
        digest = hashlib.sha256((root / bundle).read_bytes()).hexdigest()
        if digest != WORKFLOW_TRANSITION_BASELINE[target]:
            findings.append(bundle)
    if artifact_manifest_root(ARTIFACT_BASELINE) != ARTIFACT_MANIFEST_ROOT:
        findings.append("artifact-manifest-root")
    lock_payload = json.dumps(
        [
            ADMISSION_PROTOCOL,
            BEHAVIOR_IDENTITY,
            ARTIFACT_MANIFEST_ROOT,
            sorted(SOURCE_BASELINE.items()),
            sorted(PROOF_CLOSURE_BASELINE.items()),
            sorted(PYTHON_PATHS),
            sorted(WORKFLOW_TRANSITION_BASELINE.items()),
        ],
        separators=(",", ":"),
    ).encode("utf-8")
    if "sha256:" + hashlib.sha256(lock_payload).hexdigest() != TRUST_ROOT_LOCK_IDENTITY:
        findings.append("trust-root-lock")
    return tuple(findings)


def _required_paths() -> tuple[str, ...]:
    """Return the exact candidate paths whose blobs admission consumes."""
    return tuple(
        sorted(
            SOURCE_BASELINE
            | ARTIFACT_BASELINE
            | PROOF_CLOSURE_BASELINE
            | WORKFLOW_TRANSITION_BASELINE
            | {VALIDATOR_PATH: ""}
        )
    )


def _load_blob_directory(blob_directory: Path) -> dict[str, bytes]:
    """Load only lowercase Git object-ID filenames from a runner-owned directory."""
    blobs: dict[str, bytes] = {}
    for entry in blob_directory.iterdir():
        if not entry.is_file() or not _hex(entry.name, {40, 64}):
            raise ValueError("Blob directory contains an invalid entry")
        blobs[entry.name] = entry.read_bytes()
    return blobs


def main(argv: list[str] | None = None) -> int:
    """Run base self-check, list fixed paths, or validate candidate Git data."""
    parser = argparse.ArgumentParser()
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument("--self-check", action="store_true")
    commands.add_argument("--print-required-paths", action="store_true")
    commands.add_argument("--candidate", action="store_true")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--records", type=Path)
    parser.add_argument("--record-format", choices=("stage-v1", "tree-v1"))
    parser.add_argument("--blob-dir", type=Path)
    parser.add_argument("--base-sha")
    parser.add_argument("--validator-blob-oid")
    parser.add_argument("--validator-sha256")
    parser.add_argument("--workflow-blob-oid")
    parser.add_argument("--workflow-sha256")
    arguments = parser.parse_args(argv)
    if arguments.print_required_paths:
        print(*_required_paths(), sep="\n")
        return 0
    if arguments.self_check:
        if arguments.root is None:
            parser.error("--self-check requires --root")
        findings = self_check(arguments.root)
        if findings:
            for finding in findings:
                print(f"FAIL {finding}")
            return 1
        print(f"PASS {ADMISSION_PROTOCOL} {ARTIFACT_MANIFEST_ROOT}")
        return 0
    candidate_values = (
        arguments.records,
        arguments.record_format,
        arguments.blob_dir,
        arguments.base_sha,
        arguments.validator_blob_oid,
        arguments.validator_sha256,
        arguments.workflow_blob_oid,
        arguments.workflow_sha256,
    )
    if any(value is None for value in candidate_values):
        parser.error("--candidate requires records, blobs, format, and base identities")
    authority = BaseAuthority(
        base_sha=arguments.base_sha,
        validator_blob_oid=arguments.validator_blob_oid,
        validator_sha256=arguments.validator_sha256,
        workflow_blob_oid=arguments.workflow_blob_oid,
        workflow_sha256=arguments.workflow_sha256,
    )
    try:
        report = validate_candidate(
            raw_records=arguments.records.read_bytes(),
            record_format=arguments.record_format,
            blobs=_load_blob_directory(arguments.blob_dir),
            authority=authority,
        )
    except (OSError, ValueError) as error:
        print(f"FAIL ADMISSION-001 EXACT_BASELINE: {error}")
        return 1
    if not report.passed:
        print(*("FAIL " + finding for finding in report.findings), sep="\n")
        return 1
    print(f"PASS {report.protocol} {report.behavior_identity}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
