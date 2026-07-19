# Handoff Reconciliation

This document reconciles the original AEC handoff against the merged Slice 1
foundation (post de-projectize). It adopts **Reading C** (abstraction): AEC is
a project-agnostic mentoring foundation. Slice 1 ships no populated consumer
profile and names no specific consumer. Consumer profiles are consumer-owned
artifacts declared entirely in consumer repositories, described only in prose
here.

## Q1: Handoff sections satisfied by Slice 1

| Section | Status | Evidence (file:line) |
| --- | --- | --- |
| Lifecycle (nine-phase rail) | Satisfied | `README.md:17-20`, `docs/architecture/overview.md:5-15` |
| Gate precedence (fail-closed) | Satisfied | `README.md:22-26`, `config/workflows/ticket-to-pr.json:2-7`, `tools/validate_foundation.py:20,309-315` |
| Resolver schema | Satisfied | `schemas/resolution-decision.schema.json:1-49` |
| Canonical hash contract | Satisfied | `tools/validate_foundation.py:69-86` (`canonical_resolution_bytes`, `compute_resolution_hash`) |
| executes/mutates invariant | Satisfied | `schemas/resolution-decision.schema.json:9,12` (`const false`), `tools/validate_foundation.py:107-110` |
| Workflows MIT pin | Satisfied | `provenance/upstream-lock.json:4-10`, `docs/provenance.md:9,16-18` |
| Blueprint reference-only pin | Satisfied | `provenance/upstream-lock.json:11-17`, `docs/provenance.md:10,20-25` |
| Course provenance (13 + 8 lessons) | Satisfied | `provenance/course-guidance.json`, `docs/course-traceability/README.md:6-8` |
| Foundation-gate CI | Satisfied | `.github/workflows/foundation-gate.yml:16-38` |

Note: Slice 1 now ships **no consumer profile**. The single bundled profile
previously checked into `config/projects/` is removed from the tree,
`tools/validate_foundation.py` no longer runs a `project.*` check against a
bundled profile, and `docs/consumer-contract.md` describes the profile shape
as a reference example rather than a shipped artifact.

## Q2: Sections requiring amendment (14 gaps)

| # | Gap | Mapped slice |
| --- | --- | --- |
| 1 | Measurement (what "current position" means under real telemetry) | Slice 2 |
| 2 | Threat model (full canary catalog beyond hash/mutation) | Slice 2 |
| 3 | Capability negotiation between adapters | Slice 3 |
| 4 | AEC callable interface + display form | Slice 3 |
| 5 | Strict meaning of "how come" (rationale contract) | Slice 2 |
| 6 | Learning measurement (does mentoring change behavior) | Slice 7 |
| 7 | Break-glass override path | Slice 5 |
| 8 | Concurrency / idempotency guarantees | Slice 5 |
| 9 | Foundation upgrade / rollback procedure | Slice 7 |
| 10 | Workflow families beyond ticket-to-pr | Slice 7 |
| 11 | AEC-unavailable degraded mode | Slice 3 |
| 12 | Generic state-provider contract | Slice 4 |
| 13 | Red-canary extension to full 9/9 threat-model coverage | Slice 2 |
| 14 | Adaptive advice model | Slice 7 |

Slice numbers match `docs/delivery/roadmap.md`.

## Q3: Direct conflicts

- **Handoff step 6 (extend FedJobAdvisor issue #8808)** -- violated by the
  standalone-repo pivot. AEC is now an independent repository, not a module
  living inside FedJobAdvisor. #8808 assumed an in-repo extension; that
  assumption no longer holds under Reading C.
- **"Must not reorder or replace the FedJobAdvisor dependency stack"** --
  vacuously preserved. AEC touches zero FedJobAdvisor files; the two
  repositories share no dependency graph.
- **The handoff's proposed reference-consumer pilot** -- the handoff named a
  specific consumer repository as the first pilot. Under Reading C, that named
  repository is not a consumer of AEC and AEC makes no claim about it.
  Consumer profiles are consumer-repo artifacts; whether that repository ever
  adopts AEC is a decision made in that repository, not in AEC, and is out of
  scope for this foundation.

## Q4: Smallest next slice

**Slice 2** -- the deterministic resolver, Claude/Codex parity, and the
threat-model red canaries from the handoff's Mandatory Red Canaries list (all
nine), per `docs/delivery/roadmap.md` row 2.

## Q5: Red/green proof list for Slice 2

- Nine phase golden fixtures, one per lifecycle phase (Intake, Framing, Spec,
  Plan, Build, Verify, Review, PR, Deploy), each resolving to a stable
  `resolution_hash`.
- Nine red fixtures, one per handoff-defined threat-model canary (wrong hash,
  mutating AEC, stale revision, missing evidence, unpinned capability profile,
  duplicate resolution, unavailable procedure, cross-environment leakage,
  unauthorized lifecycle write).
- A parity harness that runs the same fixture through the Claude adapter and
  the Codex adapter and asserts identical `resolution_hash` output.

## Q6: Owning branch/issue/PR pattern

One issue per slice in `docs/delivery/roadmap.md`, opened against this
repository (not FedJobAdvisor). Branch naming: `slice/<n>-<short-name>` (for
example `slice/2-resolver`). One PR per slice, gated by the `Foundation gate`
required check (`.github/workflows/foundation-gate.yml`) plus the same local
verification commands documented in `README.md`. No slice merges until its
binary exit gate in `docs/delivery/roadmap.md` is met on the exact PR head.

## Handoff canary coverage

Handoff canary coverage in merged `main`: **1 of 9**
(`test_consumer_profile_cannot_claim_aec_as_lifecycle_writer` maps to handoff
canary #9, unauthorized lifecycle write). The other 15 tests in
`tests/test_foundation_validation.py` exercise schema, provenance, and
workflow drift -- honest red canaries for those surfaces, but not the
handoff's threat-model list. Closing that gap is Slice 2 gap #13 above.
