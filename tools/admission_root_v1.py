"""Dormant base-owned admission validator over raw Git tree and blob data."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, NamedTuple, Protocol


ADMISSION_PROTOCOL = "aec-admission-v1"
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


VALIDATOR_PATH = "tools/admission_root_v1.py"
ACTIVE_WORKFLOW_PATH = ".github/workflows/candidate-admission.yml"

DECLARATION_PATH = ".github/admission/v1/source-declaration.json"
DECLARATION_SCHEMA_VERSION = "1.0.0"
DECLARATION_FIELDS = {
    "artifacts",
    "behavior",
    "proof_closure",
    "python_paths",
    "schema_version",
    "sources",
    "workflow_bundles",
    "workflows",
}
BEHAVIOR_FIELDS = {"identity", "trust_root_lock_identity"}


@dataclass(frozen=True)
class SourceDeclaration:
    """One candidate-declared statement of the exact tree it ships.

    The declaration is parsed as data. It is never imported and never executed,
    so reading it cannot run candidate code. It states what the candidate claims
    to contain; admission proves the tree agrees with that claim exactly. It is
    not a claim that the declared content is correct, which review still owns.
    """

    sources: dict[str, str]
    artifacts: dict[str, ArtifactBaseline]
    proof_closure: dict[str, FileBaseline]
    python_paths: frozenset[str]
    workflows: dict[str, str]
    workflow_bundles: dict[str, str]
    behavior_identity: str
    trust_root_lock_identity: str


def _digest(value: object) -> bool:
    """Return whether a value is one lowercase SHA-256 hexadecimal digest.

    Self-contained rather than reusing _hex, because the declaration loads at
    import time and must not depend on definition order further down the module.
    """
    return (
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _relative_path(value: object) -> bool:
    """Return whether a value is one safe repository-relative path."""
    return (
        type(value) is str
        and bool(value)
        and not value.startswith("/")
        and "\\" not in value
        and ".." not in value.split("/")
    )


def parse_declaration(raw: bytes) -> SourceDeclaration:
    """Parse one declaration as closed data without importing candidate code."""
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Declaration must be strict UTF-8 JSON") from error
    if type(payload) is not dict or set(payload) != DECLARATION_FIELDS:
        raise ValueError("Declaration fields do not match the contract")
    if payload["schema_version"] != DECLARATION_SCHEMA_VERSION:
        raise ValueError("Declaration schema_version is unsupported")

    sources = payload["sources"]
    if type(sources) is not dict or not all(
        _relative_path(path) and _digest(digest) for path, digest in sources.items()
    ):
        raise ValueError("Declaration sources are invalid")

    artifacts: dict[str, ArtifactBaseline] = {}
    if type(payload["artifacts"]) is not dict:
        raise ValueError("Declaration artifacts are invalid")
    for path, row in payload["artifacts"].items():
        if (
            not _relative_path(path)
            or type(row) is not list
            or len(row) != 2
            or type(row[0]) is not str
            or not row[0]
            or not _digest(row[1])
        ):
            raise ValueError("Declaration artifacts are invalid")
        artifacts[path] = ArtifactBaseline(row[0], row[1])

    proof_closure: dict[str, FileBaseline] = {}
    if type(payload["proof_closure"]) is not dict:
        raise ValueError("Declaration proof_closure is invalid")
    for path, row in payload["proof_closure"].items():
        if (
            not _relative_path(path)
            or type(row) is not list
            or len(row) != 2
            or row[0] not in {"100644", "100755", "120000"}
            or not _digest(row[1])
        ):
            raise ValueError("Declaration proof_closure is invalid")
        proof_closure[path] = FileBaseline(row[0], row[1])

    python_paths = payload["python_paths"]
    if (
        type(python_paths) is not list
        or not all(_relative_path(path) for path in python_paths)
        or len(set(python_paths)) != len(python_paths)
    ):
        raise ValueError("Declaration python_paths are invalid")

    workflows = payload["workflows"]
    if type(workflows) is not dict or not all(
        _relative_path(path) and _digest(digest) for path, digest in workflows.items()
    ):
        raise ValueError("Declaration workflows are invalid")

    bundles = payload["workflow_bundles"]
    if (
        type(bundles) is not dict
        or set(bundles) != set(workflows)
        or not all(_relative_path(path) for path in bundles.values())
    ):
        raise ValueError("Declaration workflow_bundles are invalid")

    if ACTIVE_WORKFLOW_PATH not in workflows:
        raise ValueError("Declaration must cover the active admission workflow")
    # The validator's primary integrity anchor is the base-owned blob identity
    # below, which a candidate cannot restate. It also carries a declared
    # digest like any other tracked .py path, so the coverage clause in
    # validate_candidate needs no special case for it either.
    if VALIDATOR_PATH not in python_paths:
        raise ValueError("Declaration must track the admission validator")

    # Derived, not structural: an aggregate digest over the candidate's own
    # golden behavior, and a lock digest over the structural constants plus
    # that aggregate. Neither can be restated to change what admission *is*
    # (the structural constants stay pinned in the validator itself), but a
    # digest of the candidate's own behavior is exactly the kind of fact a
    # candidate declares, same as every other digest in this file.
    behavior = payload["behavior"]
    if type(behavior) is not dict or set(behavior) != BEHAVIOR_FIELDS:
        raise ValueError("Declaration behavior fields do not match the contract")
    if not _digest(behavior["identity"]) or not _digest(
        behavior["trust_root_lock_identity"]
    ):
        raise ValueError("Declaration behavior digests are invalid")

    return SourceDeclaration(
        sources=dict(sources),
        artifacts=artifacts,
        proof_closure=proof_closure,
        python_paths=frozenset(python_paths),
        workflows=dict(workflows),
        workflow_bundles=dict(bundles),
        behavior_identity=behavior["identity"],
        trust_root_lock_identity=behavior["trust_root_lock_identity"],
    )


def load_declaration(root: Path) -> SourceDeclaration:
    """Load the declaration that one checked-out revision ships."""
    return parse_declaration((root / DECLARATION_PATH).read_bytes())


_BASE_ROOT = Path(__file__).resolve().parents[1]
BASE_DECLARATION = load_declaration(_BASE_ROOT)
# Retained module names so existing callers keep one vocabulary. These describe
# the base revision this validator ships inside, not a frozen forever-baseline.
SOURCE_BASELINE: dict[str, str] = BASE_DECLARATION.sources
ARTIFACT_BASELINE: dict[str, ArtifactBaseline] = BASE_DECLARATION.artifacts
PROOF_CLOSURE_BASELINE: dict[str, FileBaseline] = BASE_DECLARATION.proof_closure
PYTHON_PATHS = BASE_DECLARATION.python_paths
WORKFLOW_TRANSITION_BASELINE: dict[str, str] = BASE_DECLARATION.workflows
WORKFLOW_TRANSITION_BUNDLES: dict[str, str] = BASE_DECLARATION.workflow_bundles
# Derived aggregates, declared by the base like any other candidate fact
# rather than pinned as a base-owned structural constant (issue #65). Kept as
# module constants, in this exact "sha256:"-prefixed shape, so existing
# callers and tests that import them are unaffected by where the value lives.
BEHAVIOR_IDENTITY: str = "sha256:" + BASE_DECLARATION.behavior_identity
TRUST_ROOT_LOCK_IDENTITY: str = "sha256:" + BASE_DECLARATION.trust_root_lock_identity



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


# Derived from the base declaration rather than pinned. Tracked content can now
# change without forcing this validator to change, which is what let a source
# transition be admitted at all.
ARTIFACT_MANIFEST_ROOT = artifact_manifest_root(ARTIFACT_BASELINE)


def _authority_valid(authority: BaseAuthority) -> bool:
    """Validate explicit immutable-base authority identities."""
    return (
        _hex(authority.base_sha, {40, 64})
        and _hex(authority.validator_blob_oid, {40, 64})
        and _hex(authority.workflow_blob_oid, {40, 64})
        and _hex(authority.validator_sha256, {64})
        and _hex(authority.workflow_sha256, {64})
    )


class TreeEntry(NamedTuple):
    """One resolved (mode, content) pair, from either kind of tree view."""

    mode: str
    content: bytes


class TreeView(Protocol):
    """Uniform path -> (mode, content) view over one candidate tree.

    validate_candidate and self_check judge two physically different things
    (parsed Git tree records + blob bytes, vs. a checked-out filesystem root)
    with the same set of locally-computable rules. This is the seam: each
    side adapts its own data source to this shape once, and _verify_local
    below stays ignorant of which kind it was handed.
    """

    def paths(self) -> frozenset[bytes]: ...

    def get(self, path: bytes) -> TreeEntry | None: ...


class GitRecordTreeView:
    """One candidate Git tree, addressed by parsed records and blob bytes."""

    def __init__(
        self, by_path: Mapping[bytes, GitRecord], blobs: Mapping[str, bytes]
    ) -> None:
        self._by_path = by_path
        self._blobs = blobs

    def paths(self) -> frozenset[bytes]:
        return frozenset(self._by_path)

    def get(self, path: bytes) -> TreeEntry | None:
        record = self._by_path.get(path)
        if record is None:
            return None
        content = self._blobs.get(record.object_id)
        if content is None or git_blob_oid(
            content, len(record.object_id)
        ) != record.object_id:
            return None
        return TreeEntry(record.mode, content)


class FilesystemTreeView:
    """Git-tracked paths under one checked-out root, read straight off disk.

    Path membership comes from `git ls-files`, so self-check judges exactly
    the tracked universe validate_candidate would see in a Git tree - stray
    untracked or ignored files never enter the comparison. Mode and content
    are read from the filesystem itself, not the Git index, so a chmod or a
    regular-file-to-symlink flip with unchanged bytes is still caught even
    when nothing was staged.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._paths: frozenset[bytes] | None = None

    def paths(self) -> frozenset[bytes]:
        if self._paths is None:
            output = subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=self._root,
                check=True,
                capture_output=True,
            ).stdout
            self._paths = frozenset(
                entry for entry in output.split(b"\0") if entry
            )
        return self._paths

    def get(self, path: bytes) -> TreeEntry | None:
        try:
            candidate = self._root / path.decode("utf-8")
            if candidate.is_symlink():
                return TreeEntry("120000", candidate.readlink().as_posix().encode())
            if not candidate.is_file():
                return None
            mode = "100755" if candidate.stat().st_mode & 0o111 else REGULAR_MODE
            return TreeEntry(mode, candidate.read_bytes())
        except OSError:
            return None


def _verify_local(view: TreeView) -> tuple[tuple[str, ...], SourceDeclaration]:
    """Run every admission check computable from one tree view alone.

    Shared by validate_candidate (a parsed Git tree) and self_check (a
    checked-out filesystem root): declaration presence and parse at the
    checked root, structural coverage (python_paths / tracked .json / tracked
    workflow completeness, and the python_paths-subset-of-sources|
    proof_closure invariant), the expected-path subset check, and a
    byte-exact mode+digest match for every path the declaration binds.
    Excludes the three checks that need CI-supplied base authority (argument
    well-formedness, validator identity, workflow identity) - those have no
    local analogue and stay in validate_candidate only.

    Falls back to BASE_DECLARATION when the view's own declaration is
    missing, non-regular, or unparseable, so every other check still runs
    against a trusted baseline instead of silently no-op'ing.
    """
    findings: list[str] = []
    declared = BASE_DECLARATION
    declaration_entry = view.get(DECLARATION_PATH.encode())
    if declaration_entry is None or declaration_entry.mode != REGULAR_MODE:
        findings.append(DECLARATION_PATH)
    else:
        try:
            declared = parse_declaration(declaration_entry.content)
        except ValueError:
            findings.append(DECLARATION_PATH)

    paths = view.paths()
    tracked_python = {
        path.decode()
        for path in paths
        if path.endswith(b".py")
        and (b"/" not in path or path.startswith((b"aec/", b"tests/", b"tools/")))
    }
    if tracked_python != declared.python_paths:
        findings.append("python_paths")
    # A .py path can be listed in python_paths yet omitted from every digest
    # source (sources/proof_closure), in which case the loop below never
    # hashes it at all: it is declared but never actually verified. Coverage
    # is derived from the tree's own python_paths, so a deleted file simply
    # drops out of tracked_python above and needs no special case here.
    if not declared.python_paths <= (
        set(declared.sources) | set(declared.proof_closure)
    ):
        findings.append("python_paths-coverage")

    expected_sources = {
        path.encode(): digest for path, digest in declared.sources.items()
    }
    expected_artifacts = {
        path.encode(): artifact.sha256 for path, artifact in declared.artifacts.items()
    }
    expected_closure = {
        path.encode(): baseline for path, baseline in declared.proof_closure.items()
    }
    expected_workflows = {
        path.encode(): digest for path, digest in declared.workflows.items()
    }

    # The declaration cannot carry its own digest, so it is the one tracked JSON
    # file excluded from the artifact set. Its bytes are still bound to the tree
    # record above, so a swapped declaration is still caught.
    tracked_json = {
        path for path in paths if path.endswith(b".json") and path != DECLARATION_PATH.encode()
    }
    if tracked_json != set(expected_artifacts):
        findings.append("artifacts")

    tracked_workflows = {
        path
        for path in paths
        if path.startswith(b".github/workflows/")
        and (path.endswith(b".yml") or path.endswith(b".yaml"))
    }
    if tracked_workflows != set(expected_workflows):
        findings.append("workflows")

    expected = (
        expected_sources
        | expected_artifacts
        | expected_workflows
        | {path: baseline.sha256 for path, baseline in expected_closure.items()}
    )
    if not set(expected).issubset(paths):
        findings.append("expected-paths")
    for path, digest in expected.items():
        expected_mode = expected_closure.get(
            path, FileBaseline(REGULAR_MODE, digest)
        ).mode
        entry = view.get(path)
        if (
            entry is None
            or entry.mode != expected_mode
            or hashlib.sha256(entry.content).hexdigest() != digest
        ):
            findings.append(path.decode())

    return tuple(findings), declared


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

    # The candidate states the exact tree it ships. This is read as data only.
    # Nothing here imports or executes candidate code, so ADMISSION-002 holds.
    # The base still owns the validator and workflow identities checked below,
    # so a candidate cannot restate the gate that judges it.
    local_findings, declared = _verify_local(GitRecordTreeView(by_path, blobs))
    if local_findings:
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
    ordered = tuple(outcome for outcome in OUTCOMES if outcome in findings)
    return AdmissionReport(
        base_authority=authority,
        behavior_identity="sha256:" + declared.behavior_identity,
        findings=ordered,
        passed=not ordered,
    )


def self_check(root: Path) -> tuple[str, ...]:
    """Verify the checked-out filesystem against its own trusted declaration.

    Runs every locally-computable admission check (_verify_local, shared with
    validate_candidate) directly against `root`, then layers two checks that
    have no candidate analogue: the staged future-workflow-bundle content
    match, and the validator's own frozen protocol-identity lock. This proves
    the checked-out bytes are internally consistent with their own
    declaration; it does NOT prove admissibility, which additionally needs
    the CI-supplied base authority that only validate_candidate receives (see
    main()'s printed self-check line).
    """
    view = FilesystemTreeView(root)
    local_findings, declared = _verify_local(view)
    findings: list[str] = list(local_findings)
    for target, bundle in declared.workflow_bundles.items():
        entry = view.get(bundle.encode())
        digest = hashlib.sha256(entry.content).hexdigest() if entry is not None else None
        if digest != declared.workflows.get(target):
            findings.append(bundle)
    # The lock covers only what must never move. Tracked content now lives in
    # the declaration, so pinning content here would force this validator to
    # change on every content change, and a changed validator can never pass the
    # base-owned blob identity above. That circularity is what issue #49 fixed.
    #
    # BEHAVIOR_IDENTITY and TRUST_ROOT_LOCK_IDENTITY are no longer base-pinned
    # constants (issue #65): they are read from `declared`, the same
    # declaration _verify_local already parsed for this tree. This check now
    # proves the declaration is internally self-consistent -- its declared
    # lock digest actually is the hash of the structural constants plus its
    # own declared behavior digest -- not that any particular value was used.
    # A candidate can still declare any behavior_identity it wants (that is
    # the point: it is the candidate's own fact to declare), but it cannot
    # pair it with a trust_root_lock_identity that does not match.
    lock_payload = json.dumps(
        [
            ADMISSION_PROTOCOL,
            "sha256:" + declared.behavior_identity,
            DECLARATION_PATH,
            DECLARATION_SCHEMA_VERSION,
            VALIDATOR_PATH,
            ACTIVE_WORKFLOW_PATH,
            list(OUTCOMES),
        ],
        separators=(",", ":"),
    ).encode("utf-8")
    if (
        "sha256:" + hashlib.sha256(lock_payload).hexdigest()
        != "sha256:" + declared.trust_root_lock_identity
    ):
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
            | {VALIDATOR_PATH: "", DECLARATION_PATH: ""}
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
        # Deliberately NOT shaped like validate_candidate's PASS line (which
        # carries an authority-bound behavior_identity) and NOT a digest over
        # only part of what was checked (the old artifact_manifest_root line
        # stayed byte-identical while a source file was dropped from the
        # declaration and tampered - see issue #49). This line instead names,
        # in one machine-greppable sentence, what self-check does not prove.
        print(
            f"PASS {ADMISSION_PROTOCOL} SELF-CHECK-ONLY "
            "admissibility-not-proven:validator+workflow-base-authority-unverified"
        )
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
