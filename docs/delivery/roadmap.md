# Delivery Roadmap

The foundation is intentionally delivered in reversible vertical slices.
Use the [milestone runbook](../runbooks/milestone.md) to turn a slice into one
live issue queue with explicit PR or blocker outcomes.

| Slice | Outcome | Binary exit gate |
| --- | --- | --- |
| 1. Foundation contract | Lifecycle, provenance, course inventory, resolution schema, canonical hash, red canaries, and the foundation gate CI. No consumer profile is shipped; consumer profiles live in consumer repos. | `python3 tools/validate_foundation.py` and unit tests pass on the exact PR head |
| 2. Resolver | Current consumer record resolves one procedure, reason, evidence request, good, finished, and anti-example | Golden decisions cover all nine phases, unavailable procedures fail closed, and the base-owned admission proof rejects authority, closure, path, artifact, and behavior drift |
| 3. Agent adapters | Claude and Codex render the same normalized card | Real loaders produce identical decision hashes without duplicate discovery |
| 4. Consumer interface | Caller-owned state maps into one normalized card without mutation | Green and honest red fixtures bind state to revision, environment, and freshness |
| 5. Offline Review Evidence | Normalized offline review evidence is verified without granting authority | Valid evidence is authenticated and normalized; stale, malformed, mismatched, or authority-claiming evidence fails closed |
| 6. Consumer adoption | A reference consumer integrates AEC without moving its state authority into AEC | The consumer proves its own writer, ledger, release, and audit evidence while AEC remains read-only |
| 7. Productization | Versioned release and reusable onboarding contract | A second consumer integrates without copying policy or weakening proof |

The target human and agent interaction, its current gaps, and the trustworthy-beta
release gate are defined in
[Coaching interaction](../architecture/coaching-interaction.md). That document is a
delivery contract, not a claim that the one-command coaching interface, learner profile,
or second-consumer proof already exists.

## Current position

Slices 1 through 5 are merged. Slice 2 now has deterministic goldens for all nine
lifecycle phases, an unavailable-procedure blocked tracer, malformed-request rejection,
and versioned decision bindings for the complete normalized request and procedure
catalog. RESOLVE-007 adds the base-owned admission proof and hostile corpus.
RESOLVE-009 adds deterministic fail-closed blocker precedence. Together they complete
the Slice 2 binary exit gate and closed issue
[#6](https://github.com/jasonewillis/AEC/issues/6).

Slice 3 installs the seven exact pinned Blueprint skills under one canonical
`.agents/skills/` root, with Claude symlinks and deterministic integrity validation.
The real-loader parity harness proves Claude and Codex bind the same normalized request,
manifest, and authoritative decision hash; parity issue
[#32](https://github.com/jasonewillis/AEC/issues/32) is closed. Slice 4 defines a closed
project-neutral consumer-state record and pure adapter into the resolver. Invalid,
stale, mismatched, effectful, and private-path state returns no card. Accepted state
renders one non-authoritative card and transition draft; consumer-interface issue
[#5](https://github.com/jasonewillis/AEC/issues/5) is closed.

**AEC Slice 5 - Offline Review Evidence** merged in
[PR #41](https://github.com/jasonewillis/AEC/pull/41) at main revision
`88b5f5009b9cb9ae150b94282d8db8681cb98abc`, closing
[#20](https://github.com/jasonewillis/AEC/issues/20). It verifies normalized offline
review evidence without granting execution, review, merge, or lifecycle authority.
Consumer single-writer, Project, merge, deployment, and ledger work stays outside AEC
in each consumer repository.

HealthRAG adoption exposed the remaining Slice 6 and Slice 7 productization gaps:
routine-only connection proof can miss a material-decision incompatibility and normal
use still requires consumer-authored state. AEC now owns the canonical human renderer
and the framework-side prompt-hook entrypoint; no consumer is configured by that fact.
Each consumer must still migrate the versioned human heading, pin the revision, provide
fresh revision-bound state, and register the read-only hook. Resolve the framework
admission blocker first, then deliver consumer adoption, compatibility proof, learner
boundary, outcome interaction, and the two-consumer pilot in the sequence defined by
the coaching-interaction contract.

## Completion rule

AEC is not complete when repository scaffolding exists. It is complete for a framework
release only when deterministic cross-agent guidance, consumer-owned state,
red-capable resolution, and non-authoritative offline-review evidence pass on the exact
release revision. A consumer adoption is complete only when that consumer separately
proves its single writer, lifecycle ledger, merge, deployment, and reconciliation.
