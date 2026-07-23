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
| Lifecycle (nine-phase rail) | Satisfied | `README.md:17-20`, `config/workflows/ticket-to-pr.json:10-15` |
| Gate precedence (fail-closed) | Satisfied | `README.md:22-26`, `config/workflows/ticket-to-pr.json:2-7`, `tools/validate_foundation.py:20,309-315` |
| Resolver schema | Satisfied | `schemas/resolution-decision.schema.json:1-49` |
| Canonical hash contract | Satisfied | `tools/validate_foundation.py:69-86` (`canonical_resolution_bytes`, `compute_resolution_hash`) |
| executes/mutates invariant | Satisfied | `schemas/resolution-decision.schema.json:9,12` (`const false`), `tools/validate_foundation.py:107-110` |
| Workflows MIT pin | Satisfied | `provenance/upstream-lock.json:4-10`, `docs/provenance.md:9,16-18` |
| Blueprint authorized skill pin and real Claude/Codex parity | Satisfied; exact canonical skill bytes, discovery paths, loader evidence, normalized request, manifest, and decision hash agree | `provenance/upstream-lock.json`, `provenance/blueprint-skills.json`, `.agents/skills/`, `.claude/skills/`, `tests/test_agent_adapters.py`, closed parity issue [#32](https://github.com/jasonewillis/AEC/issues/32); complementary consumer-interface issue [#5](https://github.com/jasonewillis/AEC/issues/5) is also closed |
| Factual course provenance (13 + 8 lessons) | Satisfied | `provenance/course-inventory.json`, `docs/course-traceability/README.md` |
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
| 7 | Break-glass override path | Consumer-owned; outside AEC |
| 8 | Concurrency / idempotency guarantees | Consumer-owned; outside AEC |
| 9 | Foundation upgrade / rollback procedure | Slice 7 |
| 10 | Workflow families beyond ticket-to-pr | Slice 7 |
| 11 | AEC-unavailable degraded mode | Slice 3 |
| 12 | Generic state-provider contract | Slice 4 |
| 13 | End-to-end closure of all nine routed canaries | AEC plus consumer adoption |
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

## Q4: Framework delivery status

**AEC Slice 5 - Offline Review Evidence** merged in
[PR #41](https://github.com/jasonewillis/AEC/pull/41) at main revision
`88b5f5009b9cb9ae150b94282d8db8681cb98abc`, closing
[#20](https://github.com/jasonewillis/AEC/issues/20). Slices 1 through 5 have no open
implementation issue. Slice 2 is complete under closed
[#6](https://github.com/jasonewillis/AEC/issues/6), real Claude/Codex parity is
complete, and consumer single-writer work remains outside AEC.

## Q5: Slice 2 proof after #6

- Nine phase golden fixtures, one per lifecycle phase (Intake, Framing, Spec, Plan,
  Build, Verify, Review, PR, Deploy), resolve to stable decision hashes.
- Unavailable procedures and active blockers produce deterministic blocked decisions.
- The base-owned admission proof rejects candidate self-authorization, governed-source
  closure drift, hostile Git paths and modes, ambiguous artifacts, and behavior drift.
- RESOLVE-009 proves blocker precedence is deterministic and order independent.
- Claude and Codex parity remains a separate completed Slice 3 proof.

## Q6: Owning branch/issue/PR pattern

One issue per slice in `docs/delivery/roadmap.md`, opened against this
repository (not FedJobAdvisor). Branch naming: `slice/<n>-<short-name>` (for
example `slice/2-resolver`). One PR per slice, gated by the `Foundation gate`
required check (`.github/workflows/foundation-gate.yml`) plus the same local
verification commands documented in `README.md`. No slice merges until its
binary exit gate in `docs/delivery/roadmap.md` is met on the exact PR head.

## Handoff canary routing after #6

Issue #6 defines the authoritative nine-canary catalog. Slice 2 closes its
resolver-owned outcomes, but it does not make every transferred consumer outcome an AEC
claim. Current evidence is recorded per identity instead of forcing a misleading
aggregate percentage.

| # | Exact #6 canary identity | Status | Current owner evidence |
| ---: | --- | --- | --- |
| 1 | Unavailable skill | Proven in AEC | `test_unavailable_skill_returns_one_stable_blocked_decision` and closed [#6](https://github.com/jasonewillis/AEC/issues/6) |
| 2 | Duplicate skill discovery | Proven in AEC | `test_duplicate_codex_skill_name_fails_closed`, Claude duplicate-loader rejection, and closed parity [#32](https://github.com/jasonewillis/AEC/issues/32) |
| 3 | Wrong-revision evidence | Proven in AEC | The resolver binds wrong-revision evidence without allowing it to satisfy the current request; closed [#6](https://github.com/jasonewillis/AEC/issues/6) |
| 4 | Stale lifecycle phase | Transferred | AEC proves deterministic handling of normalized `LIFECYCLE_STATE_STALE`; authoritative detection belongs to closed consumer writer [#8807](https://github.com/JLWAI/fedJobAdvisor/issues/8807) |
| 5 | Missing browser capability | Open integration evidence | The #6 route points to closed AEC [#5](https://github.com/jasonewillis/AEC/issues/5), but #5 proves consumer-state adaptation, not a browser-capability canary. Closed parity [#32](https://github.com/jasonewillis/AEC/issues/32) proves loader evidence, not browser availability. |
| 6 | Conflicting project policy | Proven in AEC | `POLICY_CONFLICT` is in the closed blocker registry and deterministic precedence proof under closed [#6](https://github.com/jasonewillis/AEC/issues/6) |
| 7 | Private-file inclusion | Proven at the AEC boundary; consumer-owned beyond it | Private-path consumer-state fixtures reject before resolution under closed [#5](https://github.com/jasonewillis/AEC/issues/5); consumer adapter [#8808](https://github.com/JLWAI/fedJobAdvisor/issues/8808) is closed |
| 8 | Label green while evidence is red | Open integration evidence | Labels are consumer state. The routed consumer writer [#8807](https://github.com/JLWAI/fedJobAdvisor/issues/8807) is closed, but its current contract does not provide linked binary proof of contradictory green-label removal. |
| 9 | Duplicate or unauthorized lifecycle writer | Transferred | AEC rejects profiles that name AEC as writer; authenticated single-writer enforcement belongs to closed consumer writer [#8807](https://github.com/JLWAI/fedJobAdvisor/issues/8807) |

The RESOLVE-007 hostile corpus adds separate admission-boundary protection. Existing
wrong-hash, mutation, schema, provenance, and cross-environment integrity tests also
remain required, but none substitute for the exact catalog above. End-to-end
integration cannot claim all nine green while canaries 5 and 8 lack linked binary
acceptance evidence.
