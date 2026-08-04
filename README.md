# Agentic Engineering Coach

AEC is an agent-agnostic mentoring and conformance layer for software delivery.
It gives Claude, Codex, and future agents the same answer to four questions:

1. Where is this task in the delivery lifecycle?
2. What is the earliest unmet gate?
3. Which locally installed procedure fits next?
4. What observable evidence permits movement?
5. What should the engineer learn and recognize next time?
6. At a material fork, what are the choices, tradeoffs, recommendation, and owner?

AEC is not a coding agent, lifecycle writer, deployment system, or second project
tracker. It resolves a deterministic, non-mutating recommendation. The consuming
project owns execution, evidence, state, and release authority.

## Lifecycle

```text
UNDERSTAND               DESIGN               EXECUTE               ASSURE & RELEASE
[Intake] -> [Framing] -> [Spec] -> [Plan] -> [Build] -> [Verify] -> [Review] -> [PR] -> [Deploy]
```

Gate precedence is fail-closed:

```text
Blocked > Needs review > Evidence needed > Ready
```

## Foundation slice

This repository currently provides:

- a versioned ticket-to-PR workflow registry;
- deterministic request, procedure-catalog, rejection, and decision schemas plus a
  canonical SHA-256 contract with normalized request and catalog input bindings and
  exactly one primary procedure or blocker;
- a pure nine-phase resolver catalog with immutable mentoring-card results;
- a prompt-hook renderer that displays one validated workflow rail, project guidance,
  and mentoring block at meaningful triggers, uses a compact indicator for routine
  progress, and makes unavailable consumer state explicit;
- AEC-authored phase teaching plus optional, validated material-decision support with
  declared evidence quality, confidence, principal uncertainty, and one expected
  measurable result;
- a hashed public mentoring card whose closed validator recomputes local structural and
  tamper integrity, without signing keys, secrets, or any claim of external origin;
- a local-only outcome receipt and deterministic evaluator that derive each verdict from
  an exact integer result measured after the change, without telemetry, free text, or
  causal claims;
- provenance locks for upstream pattern sources;
- seven exact, pinned Blueprint skills under one canonical agent-neutral root with
  Claude symlinks and fail-closed hash and discovery-parity validation;
- factual-only provenance for 13 AI Engineer lessons, one supplemental gateway PDF,
  and eight Evals & Monitoring lessons with honestly unverified hashes;
- an independently authored AEC principle registry with no course-to-policy mapping;
- honest red fixtures for malformed requests, tampered decisions, mutation, and hash
  defects; and
- standard-library validation that runs without installing dependencies.

The same commands run in the required `Foundation gate` GitHub Actions workflow.

Run the acceptance gate:

```bash
python3 tools/validate_foundation.py
python3 -m unittest discover -s tests -v
```

Render one validated local checkpoint:

```bash
python3 -m tools.aec_coach state \
  --task aec#81 --phase PR --lane INFRA --out tmp/aec-state.json
printf '%s' '{"hook_event_name":"UserPromptSubmit","prompt":"show AEC status","aec_trigger":"status-request"}' |
  python3 tools/aec_prompt_hook.py \
    --state tmp/aec-state.json \
    --project-root "$PWD" \
    --environment local
```

Consumer projects own their state producer and hook registration. A missing or rejected
state emits `[AEC: Integration Blocked]`; AEC does not infer a phase from prompt text.
Native prompt-hook payloads omit `aec_trigger` and receive compact routine output. A
consumer-owned adapter selects a closed trigger per interaction and adds `aec_trigger`
before invoking AEC; a static hook argument cannot provide dynamic trigger behavior.
The framework hook alone does not change any consumer. Human-render contract `1.5.0`
retains `[AEC: Mentoring]` and adds deterministic full/compact presentation. Consumers
must explicitly pin and validate the candidate AEC revision before adopting it.

## Releases and consumer update notifications

AEC publishes reviewed versions as GitHub Releases, never as a floating `main` pin. Each
release attaches:

- `aec-release-manifest.json`, a closed machine-readable record containing the exact tag
  commit, contract versions, release channel, compatibility posture, and required
  consumer probes; and
- `release-manifest.schema.json`, the matching public schema.

The exact revision is generated from the immutable tag commit during publication. It is
not stored in a self-referential tracked file. Consumers may poll the official
`jasonewillis/AEC` release feed and open their own update pull requests, but must validate
the candidate at that exact SHA. The manifest sets `auto_merge_allowed=false`; AEC never
edits, merges, deploys, or changes lifecycle state in a consumer repository.

Publication requires the protected `AEC_RELEASE_TOKEN` repository secret with
Administration read access and Contents write access. The workflow fails before creating
a release unless repository release immutability is enabled.

## Documentation

**Architecture** — what AEC is and what it refuses to do.

- [Overview](docs/architecture/overview.md)
- [Operating model](docs/architecture/operating-model.md)
- [Coaching interaction](docs/architecture/coaching-interaction.md) — target interaction,
  gap map, and the trustworthy-beta release gate
- [Consumer contract](docs/architecture/consumer-contract.md)
- [Deterministic resolver](docs/architecture/resolver.md)
- [Agent adapter parity](docs/architecture/agent-adapters.md)
- [Decision outcomes](docs/architecture/decision-outcomes.md)
- [Private course lens](docs/architecture/private-course-lens.md)

**Adopting AEC** — start here if you are wiring a consumer repository.

- [Register the read-only hook](docs/consumer-kit/register-hook.md)
- [Ticket-to-PR workflow](docs/workflows/ticket-to-pr.md)
- [Milestone runbook](docs/runbooks/milestone.md)

**Provenance and delivery**

- [Provenance and licensing](docs/provenance.md)
- [Course traceability](docs/course-traceability/README.md)
- [Delivery roadmap](docs/delivery/roadmap.md)
- [Release notes](docs/releases/v0.1.0.md)

**History** — closed audit artifacts, retained for provenance. Do not read these as
current status; each carries a closure header saying what has since changed.

- [Handoff reconciliation](docs/history/handoff-reconciliation.md)
- [FedJobAdvisor migration map](docs/history/fedjobadvisor-migration-map.md)

## Source boundaries

AEC-authored content is MIT licensed. `owainlewis/workflows` is a pinned MIT-licensed
pattern source. The seven `owainlewis/blueprint` skills are installed byte-for-byte at
the pinned revision under the repository owner's attestation of direct permission from
Owain Lewis as the course creator. Blueprint has no verified upstream license, and the
permission record is not an MIT claim. Tracked private course records remain limited to
factual identifiers, exact titles, source filenames, and verified hashes. An
owner-authorized local ignored lens may add private mentoring context after resolution,
but it cannot define runtime policy, change the decision hash, or authorize execution.
AEC ships no populated consumer profile; consumer profiles
are declared and owned entirely in consumer repositories. See
[provenance](docs/provenance.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
