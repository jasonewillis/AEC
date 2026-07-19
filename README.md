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
- a deterministic resolver-decision schema and canonical SHA-256 contract;
- provenance locks for upstream pattern sources;
- traceability for 13 AI Engineer lessons and eight Evals & Monitoring lessons;
- honest red fixtures for mutation and hash defects;
- a consumer profile for `jasonewillis/jwTravelScanner`; and
- standard-library validation that runs without installing dependencies.

The same commands run in the required `Foundation gate` GitHub Actions workflow.

Run the acceptance gate:

```bash
python3 tools/validate_foundation.py
python3 -m unittest discover -s tests -v
```

## Documentation

- [Architecture](docs/architecture/overview.md)
- [Operating model](docs/operating-model.md)
- [Ticket-to-PR workflow](docs/workflows/ticket-to-pr.md)
- [Course traceability](docs/course-traceability/README.md)
- [Provenance and licensing](docs/provenance.md)
- [Consumer contract](docs/consumer-contract.md)
- [Delivery roadmap](docs/delivery/roadmap.md)

## Source boundaries

AEC is independently authored. `owainlewis/workflows` is a pinned MIT-licensed
pattern source. `owainlewis/blueprint` is a pinned reference-only capability index
because this project has not verified an adoption license. Course materials inform
original operating principles but are not copied into runtime prompts or distributed
from this repository. See [provenance](docs/provenance.md).
