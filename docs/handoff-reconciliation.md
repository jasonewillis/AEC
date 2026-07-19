# Agent-Agnostic Foundation Handoff — Reconciliation with AEC `main`

**Reconciled head:** `a280fa59e8afa15b6f86833d9027445c73c30c57` (squash of PR #2, exact-reviewed `e6c4152c69fa5646355b93667bd0cc37df60fccd`).
**Handoff source:** `jwProjects` worktree branch `codex/aec-agent-agnostic-handoff`, commit `86e78a9`, at `jwEducation/jwAgenticEngineering/docs/aec/agent-agnostic-foundation-handoff.md`.
**Reading adopted:** **A — pivot.** AEC is now a standalone private repository (`jasonewillis/AEC`) with jwTravelScanner as the first consumer. The handoff's prescription to extend FedJobAdvisor `#8808` first is superseded by that decision. FedJobAdvisor integration remains a separate track owned by its own repo and issues; it is not blocked on AEC and AEC is not blocked on it.

The handoff's "Main-thread completion response" requires answering six questions. This document answers them against the merged content on the exact head above.

## Q1. Which existing artifacts already satisfy each handoff section?

| Handoff section | Satisfied by |
|---|---|
| Canonical lifecycle (4 stages / 9 phases) | `README.md:17-19`, `config/workflows/ticket-to-pr.json:10-15`, `docs/workflows/ticket-to-pr.md:8-19`, `tools/validate_foundation.py:44-60`, `schemas/resolution-decision.schema.json:13,24` |
| Gate precedence (`Blocked > Needs review > Evidence needed > Ready`) | `config/workflows/ticket-to-pr.json:2-7`, `tools/validate_foundation.py:20,309-315`, `docs/workflows/ticket-to-pr.md:22-33` |
| Resolver decision schema + canonical hash | `schemas/resolution-decision.schema.json` (19 required fields), `tools/validate_foundation.py:69-155` (canonical serialization: UTF-8, sorted keys, compact separators; SHA-256; `sha256:<hex>` form) |
| `executes=false` / `mutates=false` invariant | `schemas/resolution-decision.schema.json:9,12` (`const: false`), `tools/validate_foundation.py:107-110` (`is not False` — rejects null/0/"false"/truthy strings) |
| Provenance policy (Workflows MIT pattern-source; Blueprint reference-only) | `provenance/upstream-lock.json`, `docs/provenance.md`, `tools/validate_foundation.py:158-207` |
| Course provenance (13 AI Engineer + 8 Evals & Monitoring lessons, IDs, principles, phase mapping) | `provenance/course-guidance.json`, `docs/course-traceability/README.md`, `tools/validate_foundation.py:210-266` |
| AEC read-only / consumer-owned lifecycle authority | `AGENTS.md:5-11`, `config/projects/jwtravelscanner.json:2,7`, `tools/validate_foundation.py:319-353`, `docs/consumer-contract.md` |
| Foundation-owned vs consumer-owned responsibility boundaries | `docs/architecture/overview.md:19-25`, `docs/consumer-contract.md:7-24` |
| Red canaries against schema / provenance / workflow drift | `tests/fixtures/resolution.wrong-hash.json`, `tests/fixtures/resolution.mutating-aec.json`, `tests/test_foundation_validation.py` (wrong-hash, mutating-AEC, skipped-phase, missing-course-lesson, blueprint-adoption-without-license, duplicate-upstream, invalid-gate/reason, AEC-cannot-claim-writer). These are honest red canaries per `AGENTS.md:37` ("A green-only check is not a proof harness. Every critical gate needs a red canary.") but they exercise Slice 1's contract surface, **not** the handoff's threat-model canary list. See row below for coverage of the handoff's 9. |
| Handoff's "Mandatory red canaries" list (9 items) | **1 of 9 partially covered.** Only `test_aec_cannot_claim_consumer_lifecycle_authority` maps to the handoff's #9 (*duplicate or unauthorized lifecycle writer*), and even then only via profile-authority validation — not runtime duplicate-writer detection. The other 8 handoff canaries (unavailable skill, duplicate skill discovery, wrong-revision evidence, stale lifecycle phase, missing browser capability, conflicting project policy, private-file inclusion, label-green-while-evidence-red) require concepts (skills, capabilities, evidence records, lifecycle state, projections) that arrive in Slices 2–5. See Q2 amendment #13. |
| Migration constraint (handoff: "FedJobAdvisor currently treats `.agents/skills/fja-*` as canonical … Preserve that contract during the current integration.") | **Vacuously preserved** under Reading A. The AEC repo is a separate GitHub repository (`jasonewillis/AEC`) with no files under `.agents/`, `.claude/`, or `.codex/`. It cannot modify FJA's skill-root contract because it does not touch the FJA repository at all. Preservation is a byproduct of decoupling, not an act of enforcement. |
| Schema/validator field-parity gate | `tests/test_foundation_validation.py:61-64` |
| Auto-merge deferred / AEC cannot merge or deploy | `AGENTS.md:5-11`, `docs/architecture/overview.md:19-25`, `docs/workflows/ticket-to-pr.md:38-43`, `docs/operating-model.md:56-66` |
| Foundation gate CI, read-only permissions | `.github/workflows/foundation-gate.yml:9-10` (`contents: read`), `fetch-depth: 2`, no write scopes |

**Bottom line:** the merged foundation satisfies the handoff's **contract and licensing layers**. It does not satisfy the handoff's **measurement, threat-model, adaptive-advice, or capability-negotiation layers** — those are addressed in Q2.

## Q2. Which sections require amendments?

Listed most-material first. Each amendment names the earliest AEC slice that should own it (references `docs/delivery/roadmap.md`).

| # | Handoff section | Current state on `main` | Amendment | Owning slice |
|---|---|---|---|---|
| 1 | **Effectiveness measurement from day one** (universal health / project outcome / mentor quality / learner development / friction) | Absent | Add `schemas/measurement-event.schema.json` + `docs/measurement.md` defining the immutable per-task evaluation artifact contract, the four measurement layers, and the observation-vs-interpretation rule. | Slice 4 (Consumer evidence) — earliest correct point, since measurement events are consumer-produced and AEC-schema-owned. |
| 2 | **Threat model** (12 threats + prompt-injection defenses + break-glass) | Absent | Add `docs/threat-model.md` + red fixtures for prompt injection in issue bodies, wrong-revision replay, duplicate-writer, private-data leak, adapter drift. | Slice 2 (Resolver) — the resolver is the enforcement point for most of these threats. |
| 3 | **Capability negotiation** (attested manifest, digest, granted authority) | Absent | Add `schemas/capability-manifest.schema.json` + `docs/capabilities.md`. Extend project profile to consume capability declarations. | Slice 3 (Agent adapters) — the adapters are the manifest source. |
| 4 | **AEC callable interface** (`status` / `guide` / `explain` + display form `**[AEC]** **[command] …**`) | Absent | Add `docs/aec-interface.md` naming the three v0 commands, the reserved `reflect` / `audit` follow-ons, and the required display form. Add a fixture asserting the display form. | Slice 3 (Agent adapters) — the interface is what the adapters render. |
| 5 | **"How come" strict meaning + 6 W's contract** | Absent | Fold into `docs/aec-interface.md` above. Explicitly bans hidden-reasoning dumps. | Slice 3. |
| 6 | **Learning measurement** (learner prediction + teach-back before AEC reveals guidance) | Absent | Fold into `docs/measurement.md` above (learner development layer). Add `schemas/learner-profile.schema.json`. | Slice 4. |
| 7 | **Break-glass and recovery** (audited waiver with actor / reason / scope / expiration / risk / evidence) | Absent | Add `schemas/waiver.schema.json` + `docs/waivers.md`. Explicit rule that a waiver never converts missing evidence into passing evidence. | Slice 5 (Single writer) — the writer enforces waivers. |
| 8 | **Concurrency / idempotency** (task claims, optimistic locking, append-safe events, stale-resolution rejection) | Named as a threat, not enforced | Fold into Slice 5. Resolver already emits an immutable `resolution_hash` bound to inputs, which is the foundation for stale-resolution rejection; writer must enforce it. | Slice 5. |
| 9 | **Foundation upgrade / rollback / semver / compatibility contracts** | Partial (schema_version `1.0.0` fields present on 5 objects; no upgrade or lock protocol) | Add `provenance/foundation-lock.yaml` + `docs/upgrade.md` defining version-compatibility rules, rollback trigger, and per-consumer adoption cadence. | Slice 7 (Productization). |
| 10 | **Workflow families** (feature / bug / refactor / research / ops / migration / security) | One workflow (`ticket-to-pr`) | Extend `config/workflows/` with a workflow-family taxonomy schema in a later slice. Do not add more workflows until Slice 2 validates the pattern on one. | Slice 6 (Pilot) — driven by real jwTravelScanner issues. |
| 11 | **AEC not a single point of failure** | Read-only design + consumer-owned writer partially address it | Add explicit "AEC-unavailable degraded mode" note to `docs/operating-model.md`. Consumer harness must remain able to advance a task when AEC is offline. | Slice 3. |
| 12 | **Generic state-provider contract** (GH-issue / GH-Project / offline providers, all normalizing into one lifecycle schema) | Not addressed on either side (also absent from the handoff itself) | Add `schemas/state-provider.schema.json` + `docs/state-providers.md`. Deferred because jwTravelScanner uses a single provider; only becomes load-bearing at Slice 7. | Slice 7 (Productization). |
| 13 | **Red canary extension** (9 mandatory canaries per handoff) | **1 of 9 partial.** Only handoff #9 (*duplicate or unauthorized lifecycle writer*) is touched, via `test_aec_cannot_claim_consumer_lifecycle_authority`, which validates the profile-level claim only — not runtime duplicate-writer detection. The other 8 (unavailable skill, duplicate skill discovery, wrong-revision evidence, stale lifecycle phase, missing browser capability, conflicting project policy, private-file inclusion, label-green-while-red) require concepts that are not first-class in Slice 1. Slice 1's other 15 tests exercise schema / provenance / workflow drift, which is honest red-canary discipline but is a different threat surface than the handoff's threat-model list. | Add fixtures for the handoff canaries as their exercised concepts arrive: skills + capabilities in Slice 3; wrong-revision-evidence + stale-lifecycle-phase + label-green-while-red in Slice 4 (Consumer evidence); conflicting-project-policy in Slice 5 (Single writer); private-file-inclusion in Slice 2 (Resolver, as part of the injection-safe input contract, folded into gap G2). Full handoff-canary parity is a **Slice 5 exit gate**. | Slices 2–5, per concept. |
| 14 | **Adaptive advice model** (observed problem → evidence → cause → recommended change → measurement window → rollback) | Absent | Add `schemas/advice-proposal.schema.json` + `docs/adaptive-advice.md`. AEC proposals must go through the normal issue/PR flow. | Slice 6 (Pilot) — needs live measurements first. |
| 15 | **`.agentic/` neutral source tree + thin adapters + generated adapter carrying source digest** | Not adopted — AEC uses `config/` at repo root instead | Non-amendment: AEC's `config/projects/*.json` + `config/workflows/*.json` + `provenance/*.json` layout is functionally equivalent for a single-repo foundation. Adopt `.agentic/` only when a consumer needs the pattern embedded inside its own tree; document this as an intentional divergence. | Slice 7 (Productization) — revisit when a second consumer joins. |

## Q3. Direct conflict with the current integration dependency order

**Yes — two substantive conflicts. Both are named, engaged directly rather than rationalised around, and accepted under Reading A.**

### Conflict 1 — step-6 ordering (violated)

The handoff prescribes at step 6 of the "Recommended implementation sequence":

> "Implement the resolver decision schema, canonical hash, and Claude/Codex parity fixtures as the smallest extension to FedJobAdvisor issue `#8808`."

`main` reality: the resolver decision schema and canonical hash were implemented in a **standalone** `jasonewillis/AEC` repo (Slice 1) with jwTravelScanner as the first consumer. Step 6 is **violated** — this is not an ordering nit, it is the reversal the handoff explicitly named.

Rationale for accepting the violation:

1. Cleaner licensing / provenance boundary — the standalone repo carries a single MIT LICENSE and its own upstream-lock without entangling FJA's history.
2. Reproducible foundation gate — the CI on `jasonewillis/AEC` runs the validator + tests + whitespace check in <10s on a fresh clone; FJA's CI is heavier and shares scope with unrelated work.
3. Independent exact-head review possible — `PR #2` was reviewed at `e6c4152` in a fresh clone with no cached notes; the same review inside FJA would fight FJA's existing agent state.
4. jwTravelScanner is a private consumer with no active production surface — the safest first consumer for a foundation with unproven mentoring behavior.

These reasons explain why the pivot was chosen; they do not dissolve the handoff clause. The clause was overridden by a direction call outside the handoff's authority boundary, and this reconciliation records the override rather than pretending it did not happen.

### Conflict 2 — "must not reorder or replace" (engaged)

The handoff states:

> "the jwTravelScanner work **must not reorder or replace** the active FedJobAdvisor dependency stack"

Reading A's answer: AEC is a **separate GitHub repository** with no files under `.agents/`, `.claude/`, `.codex/`, or FJA's tree. It touches zero FJA files. Under the literal reading of the clause — the FJA dependency stack must not be reordered or replaced — Reading A satisfies the constraint: the AEC repo cannot reorder or replace what it does not touch.

The clause has a second reading: "must not sequence AEC ahead of FJA." Under that reading Reading A conflicts, and Conflict 1's step-6 violation is the same conflict re-stated. The reconciliation adopts the literal reading and pays the ordering cost visibly, rather than adopting the sequencing reading and claiming compliance.

### Authority note

The handoff itself warns: "A chat-thread identity is not durable authority. This handoff provides architecture and acceptance requirements, not independent authority to mutate those systems." Reading A was chosen by Jason in the AEC-Slice-1 session and merged as PR #2 with independent exact-head review at `e6c4152`. That merge is the durable authority the override rests on.

**Acknowledged cost of the pivot:** the handoff's three-issue FedJobAdvisor pilot under `#8810` is not covered by this AEC repo. If that pilot proceeds, it will need its own AEC integration proof (via Slice 3+ agent adapters, once they exist), or an explicit decision to leave FJA outside AEC. FJA-side migration constraint ("Preserve that contract during the current integration") is vacuously preserved by Reading A because AEC does not touch FJA files.

## Q4. Smallest next implementation slice

**Slice 2: Deterministic resolver + Claude/Codex parity fixtures.**

Scope, per `docs/delivery/roadmap.md` and tightened by the handoff:

- Implement `tools/resolve.py` — pure function from `(current consumer lifecycle record, project profile, capability profile, policy version, workflow registry, installed procedure registry, revision, environment, evidence references)` → one normalized resolver decision matching `schemas/resolution-decision.schema.json`.
- Enforce the handoff's precedence: `Safety/privacy/legal/credentials > project risk / actor authority > lifecycle / gate > workflow > skill > project adapter > AEC teaching preferences`.
- Emit a stable `resolution_id` derived as `resolve-` + first 32 hex chars of `resolution_hash` (per handoff §Resolver contract).
- Bind each workflow invocation to the resolution's `(id, hash)` — reject stale binding.
- Golden decision fixtures for all nine phases (`Intake` … `Deploy`).
- Red fixtures per the handoff's mandatory canary list: missing input, stale record, malformed record, duplicate procedure, unavailable procedure, phase-stage mismatch, unsupported policy version, effectful decision (`executes=true` / `mutates=true`).
- Parity harness: same trusted inputs produce byte-identical canonical bytes and the same `resolution_hash` under both a "Claude" runtime harness and a "Codex" runtime harness — proved by two independent Python entry points that share nothing but the schema and the canonical serialization spec.

Explicit non-goals for Slice 2 (per handoff and roadmap):
- No writer, no evidence collection, no telemetry export, no merge actuator, no jwTravelScanner migration, no learner-profile schema, no adaptive-advice mechanism.

## Q5. Exact red / green proof for Slice 2

Green:
```
python3 tools/validate_foundation.py                                       # existing 7 PASS lines
python3 -m unittest discover -s tests -v                                    # existing 16 tests + new resolver tests
python3 tools/resolve.py --input tests/fixtures/resolver/*.golden.json     # emits stable decisions for all 9 phases
python3 tools/parity.py --claude tests/fixtures/resolver/claude-inputs.json --codex tests/fixtures/resolver/codex-inputs.json
  # produces identical resolution_hash for every scenario
git diff --check origin/main...HEAD                                         # clean
```

Red (must exit non-zero with the specific expected error):
- `tests/fixtures/resolver/red/missing-*.json` × 9 (one per required input)
- `tests/fixtures/resolver/red/stale-record.json`
- `tests/fixtures/resolver/red/malformed-record.json`
- `tests/fixtures/resolver/red/duplicate-procedure.json`
- `tests/fixtures/resolver/red/unavailable-procedure.json`
- `tests/fixtures/resolver/red/phase-stage-mismatch.json`
- `tests/fixtures/resolver/red/unsupported-policy.json`
- `tests/fixtures/resolver/red/effectful-decision.json`
- `tests/fixtures/resolver/red/wrong-resolution-binding.json`

Each red fixture ships with a paired test asserting the specific error string, so an unrelated defect cannot make the canary look green.

## Q6. Owning branch, issue, and PR

- **Owning issue:** to be created after this reconciliation is approved. Suggested title: `[ARCH] Slice 2 — Deterministic resolver, Claude/Codex parity, exact-revision binding`. Format matches issue #1.
- **Owning branch:** to be created off `main` at `codex/slice-2-resolver` **after** the issue exists. Must not overlap with `codex/foundation-bootstrap` (already deleted).
- **Owning PR:** draft PR opened against `main` immediately on first commit, per the same TDD flow as Slice 1 (red fixture first → validator entry-point next → paired test → repeat).
- **Independent review:** required at the exact head SHA before Ready gate, per AGENTS.md and the Slice 1 precedent. No self-approval.

## Handoff status

The handoff is **acknowledged**, **partially satisfied by Slice 1**, and **directs Slice 2 through Slice 7** for the remaining coverage. The gap set is tracked in a single follow-on issue (see `docs/known-gaps.md` or the `[ARCH] Known handoff gaps` tracking issue), not one issue per gap.

This reconciliation is a design artifact only. It does not itself install any behavior. Behavior arrives with the slices it names.
