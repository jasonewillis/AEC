# Agentic Engineering Coach

AEC is an agent-agnostic mentoring and conformance layer for software delivery.
It gives Claude, Codex, and future agents the same answer to four questions:

1. Where is this task in the delivery lifecycle?
2. What is the earliest unmet gate?
3. Which locally installed procedure fits next?
4. What observable evidence permits movement?

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

## Documentation

- [Architecture](docs/architecture/overview.md)
- [Deterministic resolver](docs/architecture/resolver.md)
- [Agent adapter parity](docs/architecture/agent-adapters.md)
- [Private course lens](docs/architecture/private-course-lens.md)
- [Operating model](docs/operating-model.md)
- [Ticket-to-PR workflow](docs/workflows/ticket-to-pr.md)
- [Milestone runbook](docs/runbooks/milestone.md)
- [Course traceability](docs/course-traceability/README.md)
- [Provenance and licensing](docs/provenance.md)
- [Consumer contract](docs/consumer-contract.md)
- [Delivery roadmap](docs/delivery/roadmap.md)

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
