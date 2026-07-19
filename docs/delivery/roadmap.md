# Delivery Roadmap

The foundation is intentionally delivered in reversible vertical slices.

| Slice | Outcome | Binary exit gate |
| --- | --- | --- |
| 1. Foundation contract | Lifecycle, provenance, course inventory, resolution schema, canonical hash, red canaries, and the foundation gate CI. No consumer profile is shipped; consumer profiles live in consumer repos. | `python3 tools/validate_foundation.py` and unit tests pass on the exact PR head |
| 2. Resolver | Current consumer record resolves one procedure, reason, evidence request, good, finished, and anti-example | Golden decisions cover all nine phases and fail closed for unavailable procedures |
| 3. Agent adapters | Claude and Codex render the same normalized card | Real loaders produce identical decision hashes without duplicate discovery |
| 4. Consumer evidence | The reference consumer emits typed test, review, and deployment evidence | Green and honest red integration fixtures bind evidence to revision and environment |
| 5. Single writer | Consumer-owned authenticated writer accepts legal movement and rejects races | Compare-and-swap, replay, permission, blocker, and partial-failure tests pass |
| 6. Pilot | A real reference-consumer issue traverses the complete workflow | Ledger, projection, PR, deployment, and audit evidence reconcile with no unresolved gate |
| 7. Productization | Versioned release and reusable onboarding contract | A second consumer integrates without copying policy or weakening proof |

## Current position

Slice 1 is merged. Slice 2 now has Verify-phase success, unavailable-procedure blocked,
and malformed-request rejected tracers. These tracers do not complete Slice 2: the
eight remaining lifecycle goldens and the full threat-model canary catalog remain
required before its binary exit gate can pass.

## Completion rule

AEC is not complete when repository scaffolding exists. It is complete for a release
only when the pilot proves deterministic cross-agent guidance, consumer-owned state,
red-capable evidence, one lifecycle writer, and end-to-end reconciliation.
