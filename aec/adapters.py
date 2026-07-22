"""Pure loader-evidence parsers and normalized agent adapter receipts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec.contracts import normalize_exact_json
from aec.resolver import ResolutionRejection, resolve


EXPECTED_SKILL_NAMES = (
    "design",
    "improve",
    "milestone",
    "plan",
    "review",
    "task-to-pr",
    "test",
)
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
CODEX_ROOT = re.compile(r"^- `r([0-9]+)` = `([^`]+)`$")
CODEX_SKILL = re.compile(
    r"^- ([A-Za-z0-9][A-Za-z0-9:_-]*):.*"
    r"\(file: r([0-9]+)/([^()\s]+)/SKILL\.md\)$"
)
CLAUDE_PLUGIN_SUMMARY = re.compile(
    r"Total plugin skills loaded: ([0-9]+) "
    r"\(([0-9]+) duplicate/user-owned entries skipped\)"
)
CLAUDE_SKILL_SUMMARY = re.compile(
    r"Loaded ([0-9]+) unique skills "
    r"\(([0-9]+) unconditional, ([0-9]+) conditional, managed: ([0-9]+), "
    r"user: ([0-9]+), project: ([0-9]+), additional: ([0-9]+), "
    r"legacy commands: ([0-9]+)\)"
)


@dataclass(frozen=True)
class AdapterRejection:
    """Fail-closed loader or adapter result with one exact code."""

    code: str
    agent: str


@dataclass(frozen=True)
class LoaderEvidence:
    """Normalized metadata proving one runtime's project skill discovery."""

    agent: str
    runtime_version: str
    skill_names: tuple[str, ...]
    project_root: str
    suppressed_conflicts: int


@dataclass(frozen=True)
class AdapterReceipt:
    """Metadata-only result binding loader evidence to one AEC decision."""

    agent: str
    authoritative: bool
    code: str
    decision_hash: str | None
    discovery_count: int | None
    executes: bool
    mutates: bool
    request_hash: str | None
    runtime_version: str | None
    schema_version: str
    skill_manifest_hash: str | None
    status: str
    suppressed_conflicts: int | None

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible receipt."""
        return {
            "agent": self.agent,
            "authoritative": self.authoritative,
            "code": self.code,
            "decision_hash": self.decision_hash,
            "discovery_count": self.discovery_count,
            "executes": self.executes,
            "mutates": self.mutates,
            "request_hash": self.request_hash,
            "runtime_version": self.runtime_version,
            "schema_version": self.schema_version,
            "skill_manifest_hash": self.skill_manifest_hash,
            "status": self.status,
            "suppressed_conflicts": self.suppressed_conflicts,
        }


def _rejection(code: str, agent: str) -> AdapterRejection:
    """Return one normalized loader rejection."""
    return AdapterRejection(code=code, agent=agent)


def _input_texts(payload: object) -> list[str] | None:
    """Extract exact input-text blocks from Codex prompt-input JSON."""
    try:
        payload = normalize_exact_json(payload)
    except (TypeError, ValueError):
        return None
    if type(payload) is not list:
        return None
    texts: list[str] = []
    for message in payload:
        if type(message) is not dict:
            return None
        content = message.get("content")
        if type(content) is not list:
            continue
        for block in content:
            if type(block) is not dict:
                return None
            if block.get("type") == "input_text":
                text = block.get("text")
                if type(text) is not str:
                    return None
                texts.append(text)
    return texts or None


def parse_codex_prompt_input(
    payload: object,
    *,
    runtime_version: str,
    project_root: Path,
    suppressed_conflicts: int = 0,
) -> LoaderEvidence | AdapterRejection:
    """Parse model-free Codex prompt input into project loader evidence."""
    if not isinstance(runtime_version, str) or not runtime_version.strip():
        return _rejection("RUNTIME_VERSION_INVALID", "codex")
    if type(suppressed_conflicts) is not int or suppressed_conflicts < 0:
        return _rejection("LOADER_EVIDENCE_INVALID", "codex")
    texts = _input_texts(payload)
    if texts is None:
        return _rejection("LOADER_EVIDENCE_INVALID", "codex")

    lines = "\n".join(texts).splitlines()
    roots = {
        match.group(1): match.group(2)
        for line in lines
        if (match := CODEX_ROOT.fullmatch(line)) is not None
    }
    expected_root = str(project_root.resolve() / ".agents/skills")
    matching_root_ids = [root_id for root_id, path in roots.items() if path == expected_root]
    if len(matching_root_ids) != 1:
        return _rejection("PROJECT_SKILL_ROOT_MISSING", "codex")
    project_root_id = matching_root_ids[0]

    entries: list[tuple[str, str, str]] = []
    for line in lines:
        match = CODEX_SKILL.fullmatch(line)
        if match is not None:
            entries.append((match.group(1), match.group(2), match.group(3)))
    counts = {
        name: sum(entry_name == name for entry_name, _, _ in entries)
        for name in EXPECTED_SKILL_NAMES
    }
    if any(count > 1 for count in counts.values()):
        return _rejection("DUPLICATE_SKILL_DISCOVERY", "codex")
    project_entries = {
        name
        for name, root_id, relative_path in entries
        if root_id == project_root_id and relative_path == name
    }
    if project_entries != set(EXPECTED_SKILL_NAMES) or any(
        count != 1 for count in counts.values()
    ):
        return _rejection("SKILL_SET_MISMATCH", "codex")
    return LoaderEvidence(
        agent="codex",
        runtime_version=runtime_version.strip(),
        skill_names=EXPECTED_SKILL_NAMES,
        project_root=expected_root,
        suppressed_conflicts=suppressed_conflicts,
    )


def codex_nonproject_conflicts(
    payload: object,
    *,
    project_root: Path,
) -> tuple[str, ...] | AdapterRejection:
    """Return exact non-project skill paths that collide with AEC names."""
    texts = _input_texts(payload)
    if texts is None:
        return _rejection("LOADER_EVIDENCE_INVALID", "codex")
    lines = "\n".join(texts).splitlines()
    roots = {
        match.group(1): match.group(2)
        for line in lines
        if (match := CODEX_ROOT.fullmatch(line)) is not None
    }
    expected_root = str(project_root.resolve() / ".agents/skills")
    matching_root_ids = [root_id for root_id, path in roots.items() if path == expected_root]
    if len(matching_root_ids) != 1:
        return _rejection("PROJECT_SKILL_ROOT_MISSING", "codex")
    project_root_id = matching_root_ids[0]
    entries = [
        (match.group(1), match.group(2), match.group(3))
        for line in lines
        if (match := CODEX_SKILL.fullmatch(line)) is not None
        and match.group(1) in EXPECTED_SKILL_NAMES
    ]
    project_entries = [
        (name, relative_path)
        for name, root_id, relative_path in entries
        if root_id == project_root_id
    ]
    if sorted(project_entries) != sorted((name, name) for name in EXPECTED_SKILL_NAMES):
        return _rejection("SKILL_SET_MISMATCH", "codex")
    conflicts: list[str] = []
    for name, root_id, relative_path in entries:
        if root_id == project_root_id:
            continue
        root = roots.get(root_id)
        if root is None:
            return _rejection("LOADER_EVIDENCE_INVALID", "codex")
        path = Path(root) / relative_path / "SKILL.md"
        if not path.is_absolute():
            return _rejection("LOADER_EVIDENCE_INVALID", "codex")
        conflicts.append(str(path))
    return tuple(sorted(set(conflicts)))


def parse_claude_loader_log(
    log_text: object,
    *,
    runtime_version: str,
    project_root: Path,
) -> LoaderEvidence | AdapterRejection:
    """Parse Claude project-loader debug metadata without trusting model output."""
    if not isinstance(runtime_version, str) or not runtime_version.strip():
        return _rejection("RUNTIME_VERSION_INVALID", "claude")
    if type(log_text) is not str:
        return _rejection("LOADER_EVIDENCE_INVALID", "claude")
    expected_root = str(project_root.resolve() / ".claude/skills")
    if f"project=[{expected_root}]" not in log_text:
        return _rejection("PROJECT_SKILL_ROOT_MISSING", "claude")

    plugin_matches = CLAUDE_PLUGIN_SUMMARY.findall(log_text)
    summary_matches = CLAUDE_SKILL_SUMMARY.findall(log_text)
    if len(plugin_matches) != 1 or len(summary_matches) != 1:
        return _rejection("LOADER_EVIDENCE_INVALID", "claude")
    plugin_count, duplicate_count = map(int, plugin_matches[0])
    if plugin_count != 0 or duplicate_count != 0:
        return _rejection("DUPLICATE_SKILL_DISCOVERY", "claude")

    (
        unique_count,
        unconditional_count,
        conditional_count,
        managed_count,
        user_count,
        project_count,
        additional_count,
        legacy_count,
    ) = map(int, summary_matches[0])
    expected_count = len(EXPECTED_SKILL_NAMES)
    if (
        unique_count != expected_count
        or unconditional_count != expected_count
        or project_count != expected_count
        or any(
            value != 0
            for value in (
                conditional_count,
                managed_count,
                user_count,
                additional_count,
                legacy_count,
            )
        )
    ):
        return _rejection("SKILL_SET_MISMATCH", "claude")
    return LoaderEvidence(
        agent="claude",
        runtime_version=runtime_version.strip(),
        skill_names=EXPECTED_SKILL_NAMES,
        project_root=expected_root,
        suppressed_conflicts=0,
    )


def _manifest_hash(
    manifest: object,
    evidence: LoaderEvidence,
) -> str | None:
    """Return the canonical manifest hash when it matches loader identities."""
    try:
        manifest = normalize_exact_json(manifest)
    except (TypeError, ValueError):
        return None
    if type(manifest) is not dict or type(manifest.get("skills")) is not list:
        return None
    skills = manifest["skills"]
    if any(type(skill) is not dict for skill in skills):
        return None
    names = tuple(skill.get("name") for skill in skills)
    hashes = tuple(skill.get("sha256") for skill in skills)
    if names != evidence.skill_names or any(
        type(digest) is not str or SHA256_HEX.fullmatch(digest) is None
        for digest in hashes
    ):
        return None
    canonical = json.dumps(
        manifest,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8", errors="strict")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _terminal_receipt(
    *,
    agent: str,
    code: str,
    status: str,
) -> AdapterReceipt:
    """Return a non-authoritative receipt with no reusable decision fields."""
    return AdapterReceipt(
        agent=agent,
        authoritative=False,
        code=code,
        decision_hash=None,
        discovery_count=None,
        executes=False,
        mutates=False,
        request_hash=None,
        runtime_version=None,
        schema_version="1.0.0",
        skill_manifest_hash=None,
        status=status,
        suppressed_conflicts=None,
    )


def _loader_evidence_is_valid(evidence: LoaderEvidence) -> bool:
    """Return whether normalized loader evidence satisfies every invariant."""
    expected_roots = {
        "claude": (".claude", "skills"),
        "codex": (".agents", "skills"),
    }
    expected_suffix = expected_roots.get(evidence.agent)
    if expected_suffix is None:
        return False
    if type(evidence.runtime_version) is not str or not evidence.runtime_version.strip():
        return False
    if evidence.skill_names != EXPECTED_SKILL_NAMES:
        return False
    if type(evidence.project_root) is not str:
        return False
    project_root = Path(evidence.project_root)
    if not project_root.is_absolute() or project_root.parts[-2:] != expected_suffix:
        return False
    if (
        type(evidence.suppressed_conflicts) is not int
        or evidence.suppressed_conflicts < 0
    ):
        return False
    return evidence.agent != "claude" or evidence.suppressed_conflicts == 0


def build_adapter_receipt(
    evidence: LoaderEvidence | AdapterRejection,
    request: object,
    catalog: object,
    skill_manifest: object,
    *,
    installation_errors: tuple[str, ...],
    aec_available: bool = True,
) -> AdapterReceipt:
    """Bind trusted loader evidence to one deterministic AEC decision."""
    if type(evidence) not in (LoaderEvidence, AdapterRejection):
        return _terminal_receipt(
            agent="unknown",
            code="LOADER_EVIDENCE_INVALID",
            status="rejected",
        )
    agent = evidence.agent if evidence.agent in {"claude", "codex"} else "unknown"
    if isinstance(evidence, AdapterRejection):
        return _terminal_receipt(
            agent=agent,
            code=evidence.code,
            status="rejected",
        )
    if not _loader_evidence_is_valid(evidence):
        return _terminal_receipt(
            agent=agent,
            code="LOADER_EVIDENCE_INVALID",
            status="rejected",
        )
    if not aec_available:
        return _terminal_receipt(
            agent=agent,
            code="AEC_UNAVAILABLE",
            status="degraded",
        )
    if installation_errors:
        return _terminal_receipt(
            agent=agent,
            code="SKILL_INSTALLATION_INVALID",
            status="rejected",
        )
    manifest_hash = _manifest_hash(skill_manifest, evidence)
    if manifest_hash is None:
        return _terminal_receipt(
            agent=agent,
            code="SKILL_MANIFEST_MISMATCH",
            status="rejected",
        )
    decision = resolve(request, catalog)
    if isinstance(decision, ResolutionRejection):
        return _terminal_receipt(
            agent=agent,
            code="RESOLUTION_REJECTED",
            status="rejected",
        )
    decision_payload = decision.to_dict()
    input_bindings = decision_payload.get("input_bindings")
    if not isinstance(input_bindings, dict):
        return _terminal_receipt(
            agent=agent,
            code="RESOLUTION_BINDING_INVALID",
            status="rejected",
        )
    request_hash = input_bindings.get("resolution_request")
    if not isinstance(request_hash, str):
        return _terminal_receipt(
            agent=agent,
            code="RESOLUTION_BINDING_INVALID",
            status="rejected",
        )
    return AdapterReceipt(
        agent=agent,
        authoritative=True,
        code="ADAPTER_READY",
        decision_hash=decision.resolution_hash,
        discovery_count=len(evidence.skill_names),
        executes=False,
        mutates=False,
        request_hash=request_hash,
        runtime_version=evidence.runtime_version,
        schema_version="1.0.0",
        skill_manifest_hash=manifest_hash,
        status="ready",
        suppressed_conflicts=evidence.suppressed_conflicts,
    )
