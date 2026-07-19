# Delivery Roadmap

The foundation is intentionally delivered in reversible vertical slices.

| Slice | Outcome | Binary exit gate |
| --- | --- | --- |
| 1. Foundation contract | Lifecycle, provenance, course inventory, resolution schema, red canaries, first consumer profile | `python3 tools/validate_foundation.py` and unit tests pass on the exact PR head |
| 2. Resolver | Current consumer record resolves one procedure, reason, evidence request, good, finished, and anti-example | Golden decisions cover all nine phases and fail closed for unavailable procedures |
| 3. Agent adapters | Claude and Codex render the same normalized card | Real loaders produce identical decision hashes without duplicate discovery |
| 4. Consumer evidence | jwTravelScanner emits typed test, review, and deployment evidence | Green and honest red integration fixtures bind evidence to revision and environment |
| 5. Single writer | Consumer-owned authenticated writer accepts legal movement and rejects races | Compare-and-swap, replay, permission, blocker, and partial-failure tests pass |
| 6. Pilot | A real jwTravelScanner issue traverses the complete workflow | Ledger, projection, PR, deployment, and audit evidence reconcile with no unresolved gate |
| 7. Productization | Versioned release and reusable onboarding contract | A second consumer integrates without copying policy or weakening proof |

## Current position

Slice 1 is the active scope. Later slices may be designed in parallel, but they cannot
claim readiness until the foundation is merged and pinned. This prevents downstream
work from inventing a competing contract.

## Completion rule

AEC is not complete when repository scaffolding exists. It is complete for a release
only when the pilot proves deterministic cross-agent guidance, consumer-owned state,
red-capable evidence, one lifecycle writer, and end-to-end reconciliation.
