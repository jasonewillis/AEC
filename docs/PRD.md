# Agentic Engineering Coach Product Requirements

## Document control

- **Status:** Active product intent
- **Reviewed:** 2026-10-09
- **Baseline:** `55b6dc832ede944e23afdaf54575468b7ecf5c8f`

This is the canonical statement of what AEC must achieve for users. Architecture
documents, schemas, validators, and versioned contracts remain the technical authority
for how the product works. Historical documents remain evidence snapshots. This PRD does
not replace either category and does not create a second status ledger.

Update this PRD when product goals, release gates, ownership boundaries, supported user
journeys, or success measures change. A contract-only implementation detail does not
require a PRD change unless it changes one of those product decisions.

## Product statement

AEC is a read-only, deterministic coach for agent-assisted software delivery. It turns
caller-owned facts about a task into a validated recommendation that teaches the next
engineering step, explains the current gate, and presents bounded decision support when
the task reaches a material fork.

## Problem

AEC already has a strong deterministic foundation. Its remaining product problem is the
distance between a valid framework contract and a complete consumer experience:

1. A validated material-decision record is not fully visible in the human rendering.
2. Installation and state construction still require consumer integration work and can
   leave copied producers or fragmented commands downstream.
3. Fixed routine and material probes prove known examples, not each consumer's own
   profile, state producer, hook, and renderer path.
4. A local outcome evaluator exists, but the normal user journey does not yet guide a
   user through recording and evaluating an outcome.
5. Static mentoring cannot yet adapt explanation depth or register while keeping the
   engineering decision unchanged.
6. Real consumer proof is incomplete: one full lifecycle pilot and one independent
   installation remain open goals.

## Product principles

1. **Read-only advice.** AEC may validate, resolve, render, and evaluate supplied facts.
   It never performs the recommended procedure or mutates consumer state.
2. **Consumer authority.** The consumer owns fact collection, lifecycle state, evidence,
   permissions, execution, review, releases, and exactly one authoritative writer.
3. **Evidence before claims.** A check claimed as a control needs a canary that can
   falsify that control. Characterization tests may pin invariants without making a
   control claim. Structural validity is not semantic quality.
4. **One decision contract.** Routine work has no artificial choice menu. A material fork
   has two or three declared choices, a recommendation, uncertainty, authority, and an
   observable result.
5. **Human and machine parity.** Human presentation must expose the material facts already
   accepted by the machine contract without changing the decision hash.
6. **Local and private by default.** Required decision snapshots remain local and
   validated. Closed outcome receipts and aggregate reports contain no free text. Private
   source expression never enters tracked files, fixtures, hosted CI, or proof logs.
7. **Pinned adoption.** Consumers validate reviewed releases at exact revisions; a
   notification never authorizes adoption or grants release authority.
8. **Project neutrality.** Consumer policy stays in the consumer; AEC owns reusable
   contracts and deterministic guidance.

## Users

### Primary users

- **Engineer learning agent-assisted delivery:** needs clear next actions, reasons, and
  recognition cues without needing to understand every framework contract first.
- **Experienced engineer directing agents:** needs concise, exact-revision advice and
  honest uncertainty at material forks.
- **Consumer integrator:** needs a small, pinned integration surface, compatibility proof,
  and explicit ownership boundaries.
- **Consumer maintainer:** needs update signals and migration requirements without AEC
  changing the consumer automatically.

## Core user stories

1. As an engineer, I can ask for status and see the current phase, earliest unmet gate,
   required proof, next procedure, and why the gate matters.
2. As an engineer at a material fork, I can compare two or three real choices and see the
   recommendation, reason, evidence quality, confidence, uncertainty, falsifier, expected
   result, revisit conditions, and decision owner.
3. As a consumer integrator, I can install a pinned AEC release, verify its manifest, run
   both known probes, and prove my consumer-specific path without copying AEC contracts.
4. As a consumer maintainer, I can build state for my repository using its root and
   profile, while explicitly supplying facts AEC cannot derive.
5. As a learner, I can request a plainer or deeper explanation without changing the gate,
   recommendation, authority, or decision hash.

6. As an engineer, I can record and evaluate the observed outcome locally, separating
   project results from coaching burden and learning transfer.

## Current baseline

| Capability | Current state | Product gap |
|---|---|---|
| Pure resolver | Shipped with nine phases, deterministic hashes, blocker precedence, and red fixtures | Caller facts remain caller claims; AEC does not discover lifecycle truth |
| Consumer state | `aec-coach state` supports `--project-root`, `--profile`, evidence, blockers, and decision context | Consolidated onboarding is incomplete; observation context is supported by the pure builder but has no CLI input |
| Human renderer | Shipped rail, guidance, mentoring, observation, and decision blocks | Material decisions omit `recommendation.why`, `recommendation.falsifier`, and `context.evidence_quality` |
| Agent guidance | Intake guidance requests bounded options and tradeoffs | Guidance cannot guarantee that an agent response uses literal Pros/Cons or is semantically thoughtful |
| Pin doctor | Routine and material fixed probes run through the public path | Fixed fixtures do not prove a consumer's profile, producer, hook, privacy rules, or task state |
| Loader parity | Claude and Codex loader receipts can bind the same pinned skills and decision | Loader parity does not prove rendered human-output parity in a consumer host |
| Outcome evaluation | Pure `evaluate_outcomes` logic, closed local receipts, and `python3 -m tools.evaluate_outcomes` exist | Guided receipt creation and a complete documented outcome interaction are missing |
| Release updates | Reviewed release manifest and consumer-owned notifier exist | Consumers still own candidate validation and adoption; automatic upgrade is intentionally absent |
| Mentoring adaptation | Static canonical teaching is shipped | Optional depth and plain-language adaptation remain open (#53, #92/PR #123) |
| Consumer pilots | HealthRAG supplied bounded observations and repairs | Full lifecycle proof (#110) and a second independent install (#111) remain open |
| Semantic quality | Validators enforce a closed and complete decision shape | Open draft PR #140 demonstrates a hollow record can satisfy structural checks; this is not merged production proof |
| Admission and review controls | Foundation and admission checks are protected on the reviewed repository setting | Open #65/PR #139 and PR #118 concern control maintenance; they do not make all product work blocked. Policy also rejects unresolved high review findings even where current enforcement does not. |
| Published artifact | GitHub release v0.2.0 was observed on 2026-10-09 as immutable and published at 2026-09-02T20:00:10Z | Publication alone does not prove the trustworthy-beta product gates below |

Current evidence sources are the [coaching gap map](architecture/coaching-interaction.md),
[consumer contract](architecture/consumer-contract.md), [outcome contract](architecture/decision-outcomes.md),
and [consumer installation runbook](consumer-kit/register-hook.md). Re-run the baseline:

```bash
python3 tools/validate_foundation.py
python3 tools/generate_source_declaration.py --check
python3 -m tools.aec_coach doctor
python3 -m tools.validate_consumer_connection --self-check
python3 -m unittest discover -s tests -v
```

On `55b6dc8`, the first four commands pass; the unit suite passed 453 tests in
212.623 seconds. G1 through G6 below are future acceptance contracts and are explicitly
**NOT IMPLEMENTED** unless the baseline matrix says otherwise. Their delivery issues must
name concrete verification commands and red evidence before implementation is accepted.

## Goals and binary acceptance

### P0 — Trustworthy material-decision display

**Goal G1:** Make the human decision block complete enough for a person to assess the
same material fork the validator accepted.

1. **G1.1** A golden material-decision render displays the question and every declared
   choice with quality, risk, reversibility, maintainability, and scope tradeoffs.
2. **G1.2** The render displays the recommended choice, `recommendation.why`, declared
   `context.evidence_quality`, confidence, principal uncertainty, and falsifier.
3. **G1.3** The render displays the measurable expected result, every revisit condition,
   and the authority owner and reason.
4. **G1.4** Removing any required displayed field makes a focused test fail.
5. **G1.5** Malformed decision context, or consumer state with stale or mismatched
   revision bindings, fails closed and produces no trusted human decision block.
6. **G1.6** Routine cards still render no decision block.
7. **G1.7** Human rendering changes no canonical decision or card hash.
8. **G1.8** Consumer wording states that decision support is validated caller input; AEC
   does not independently select, score, or verify the choices.

**Recommended next slice:** implement G1 with one consumer-specific material-decision
fixture. It closes a visible trust gap within the existing contract and requires no new
schema, authority, or service.

### P0 — Consumer-specific compatibility and onboarding

**Goal G2:** Let a new consumer prove its real integration without copying an AEC-owned
state producer or mistaking fixed framework fixtures for consumer proof.

1. **G2.1** One documented flow verifies an exact release manifest, supported contract
   versions, and both framework probes before consumer adoption.
2. **G2.2** The same flow builds and checks state using the consumer's `--project-root`
   and `--profile`.
3. **G2.3** The flow exercises one routine consumer record and one material-decision
   consumer record through state, resolver, human renderer, and machine output.
4. **G2.4** A stale revision, malformed profile, unsupported contract, or missing required
   consumer fact makes the flow exit nonzero with a specific recovery action.
5. **G2.5** Consumer documentation distinguishes fixed framework probes from
   consumer-specific compatibility proof.
6. **G2.6** The supported state path can accept observation context already supported by
   the pure builder, or the documented boundary explicitly names a consumer-owned input
   mechanism that does not copy schema construction.
7. **G2.7** A consumer can register its hook without copying AEC policy, renderer logic,
   phase mappings, or required-field sets.
8. **G2.8** No step grants AEC lifecycle-write, merge, release, or deployment authority.

### P1 — Outcome interaction

**Goal G4:** Complete the user-visible recommendation-to-observation loop around the
existing local evaluator.

1. **G4.1** A documented command or callable flow creates a schema-valid local outcome
   record bound to the exact decision hash and recommended selected choice. Alternative
   choices remain unscored under the current recommendation-only receipt contract.
2. **G4.2** The required local decision snapshot may retain validated decision prose and
   task identities. The added receipt uses only closed identifiers, required choice and
   measure/unit identities, exact integer measurements, and verification bindings; it
   rejects extra free text, raw prompts, code, private paths, and personal data.
3. **G4.3** The flow verifies the record before evaluation and rejects stale bindings,
   non-canonical integer encodings, measure/unit mismatches, prohibited fields, and a
   declared verdict that disagrees with the deterministic derived verdict. Accepted
   verification facts bind to the observed post-change revision, not a stale proposal.
4. **G4.4** The evaluator deterministically derives supported, partially supported,
   unsupported, harmful, or inconclusive from the accepted measurements.
5. **G4.5** Output separates project impact, coaching value, and engineering burden.
6. **G4.6** Reports use association language and never claim that AEC caused an outcome.
7. **G4.7** Outcome data remains local and causes no resolver, policy, or lifecycle change.

### P1 — Human parity across supported hosts

**Goal G5:** Prove that supported agent hosts show the same engineering meaning.

1. **G5.1** Claude and Codex load the same exact pinned AEC sources and resolve the same
   decision hash for one routine and one material record.
2. **G5.2** Their rendered checkpoints contain the same phase, gate, required proof,
   decision choices, recommendation facts, and authority owner.
3. **G5.3** Host-specific wrapper text cannot omit or contradict a required AEC fact.
4. **G5.4** Missing loader or hook evidence produces an explicit degraded result and no
   parity claim.
5. **G5.5** Parity fixtures cover full and compact presentation separately.

### P0 — Two real consumer proofs

**Goal G3:** Demonstrate that AEC is reusable beyond its own fixtures.

1. **G3.1** HealthRAG completes one real task from Intake through Deploy using its own
   authoritative state and exact-revision evidence (#110).
2. **G3.2** The pilot records every integration defect, workaround, and AEC-versus-consumer
   owner; it does not treat a green framework test as consumer delivery proof.
3. **G3.3** A second independent consumer installs a pinned release and reaches its first
   valid checkpoint in under 30 measured minutes without copying AEC policy (#111).
4. **G3.4** Both consumers pass routine, material-decision, stale-state, and malformed-state
   probes at their adopted exact AEC revision.
5. **G3.5** Both consumers show semantically equivalent required facts in machine and human
   output; loader success alone is insufficient.
6. **G3.6** Public or hosted AEC pilot summaries and closed receipts contain no raw
   prompts, source code, private paths, secrets, health information, personal data, or
   added free-text outcome fields. Consumers retain authorized engineering evidence in
   their own boundary.

### P2 — Optional learner adaptation

**Goal G6:** Improve comprehension without changing engineering semantics.

1. **G6.1** Every phase can render an optional plain-language explanation with short,
   concrete sentences and defined domain terms (#53).
2. **G6.2** A local learner setting may select explanation depth or register, and absence
   of the setting preserves current canonical output.
3. **G6.3** Changing a learner setting cannot change phase, gate, procedure, proof,
   recommendation, authority, transition request, decision hash, or card hash.
4. **G6.4** Before implementation, the owner records a current-output sample and a numeric
   repetition threshold. Owner review of the same declared sample meets that threshold
   without hiding the transferable lesson or reason for the gate (#92/PR #123).
5. **G6.5** Adaptation remains local, contains no learner identity or free-text profile,
   and creates no remote telemetry.

## Automation ownership

| Responsibility | AEC pure core | AEC local CLI/renderer | Consumer shell or host |
|---|---:|---:|---:|
| Validate normalized contracts | Owns | Invokes | Supplies inputs |
| Derive gate and procedure | Owns | Invokes | Supplies authoritative facts |
| Author choice and recommendation | Validates and carries through | Renders | Consumer or human owner authors |
| Render validated cards | Supplies deterministic renderer | Owns presentation command | Registers hook and displays output |
| Read Git revision and local profile | No I/O | May read explicitly selected safe local facts | Defines which repository and facts are authorized |
| Infer lifecycle phase | Never | Never | Owns authoritative phase |
| Verify real evidence | Never | Checks declared bindings only | Collects and accepts evidence |
| Execute procedures | Never | Never | Owns execution |
| Write lifecycle or project state | Never | Never | One authoritative consumer writer |
| Review, merge, deploy, release | Never | Never | Consumer and human authority |
| Notify about AEC releases | Builds and validates manifest data | Supplies checker example | Release automation publishes; consumer polls and validates |
| Adopt an update | Never automatic | Never automatic | Pins exact accepted revision |
| Store and evaluate outcomes | Pure validation/evaluation | May provide local command | Owns local record and interpretation |

## Success measures

Measures are evaluated per reviewed release and across completed pilots. A pass requires
the denominator and raw local receipts; missing data is reported as unknown.

1. **Integration success:** two independent consumers pass all G3 probes at exact pins.
2. **Time to first checkpoint:** the second consumer reaches a valid checkpoint within
   30 measured minutes from a clean documented start.
3. **Decision display completeness:** 100% of required G1 fields appear in every accepted
   material-decision golden and consumer fixture.
4. **Failure discrimination:** every critical compatibility and rendering gate has at
   least one red canary that fails when its claimed control is removed or corrupted.
5. **Human parity:** required semantic fields match in 100% of supported-host parity
   fixtures.
6. **Outcome usability:** each completed pilot can create, verify, and evaluate at least
   one closed outcome record without prohibited data.
7. **Consumer burden:** record measured setup time, manual fact count, workaround count,
   and AEC-specific maintenance changes. Report these values; do not invent a universal
   target before two pilots provide a baseline.
8. **Observed usefulness:** report the closed outcome verdict distribution and burden
   distribution. Do not infer market demand, productivity causation, or revenue.

## Trustworthy-beta release gate

AEC may be described as a trustworthy beta only when all of the following are true on one
documented release candidate:

1. G1, G2, G3, G4, and G5 are fully proven with exact-revision evidence.
2. Foundation validation, the full unit suite, source declaration check, doctor, and
   consumer-specific compatibility probes pass on that candidate.
3. Each critical gate has a red canary that demonstrably turns red when the control is
   removed or corrupted.
4. Both consumer pilots complete without AEC mutating consumer state.
5. Human rendering and machine output meet G5 for supported hosts.
6. No private course expression, consumer secret, health information, or prohibited
   outcome field appears in tracked artifacts or hosted proof.
7. An independent adversarial review has no unresolved high or critical finding.
8. A reviewed immutable release manifest identifies the exact tag commit and required
   consumer probes.
9. If learner adaptation is offered, G6 invariance is proven; otherwise the feature is
   explicitly unavailable.

A published release, green fixed fixtures, or a validator pass alone does not satisfy
this gate.

## Sequencing

1. **Complete material-decision display and one consumer fixture (G1).** This is the
   smallest user-visible trust repair and the recommended next slice.
2. **Consolidate onboarding and consumer-specific proof (G2).** Reuse the existing state,
   doctor, and checkpoint commands instead of adding another state ledger.
3. **Prove rendered host parity (G5).** Stabilize the complete display before pilots use it.
4. **Expose the local outcome interaction (G4).** Keep the existing closed evaluator as
   the authority and add only the missing user path.
5. **Run HealthRAG and the independent consumer pilot (G3).** Feed defects back into the
   smallest owning layer. Early pilot diagnosis may use the existing evaluator API; beta
   acceptance must also prove the guided G4 path.
6. **Evaluate learner adaptation (G6).** Ship only if it preserves hashes and improves
   comprehension in bounded user review.

Anti-pattern linting (#96) remains an unapproved proposal until repeated user-visible
harm and a material product decision justify its semantics and maintenance cost.

Admission maintenance (#65/PR #139), interpreter isolation (PR #118), and the static
mentoring proposal (#92/PR #123) should proceed under their own issue contracts. They
block a product slice only when that slice actually depends on their changed files or a
required exact-head gate is red.

## Material product forks

### State construction boundary

| Choice | Quality | Risk | Reversibility | Maintainability | Scope |
|---|---|---|---|---|---|
| A. Consumer builds normalized state from the published schema | Valid but duplicates schema-shaped logic | Medium drift risk | High; delete the shell | Low across consumers | Low framework change |
| B. AEC derives safe schema-shaped facts; consumer supplies authoritative values | One reusable construction path | Low-to-medium boundary risk | High; retain direct schema input | High | Medium CLI change |

**Recommendation:** B. **Evidence quality:** indirect (HealthRAG report plus directly
verified builder behavior). **Confidence:** medium. **Principal uncertainty:** a second
consumer may need facts the current flags cannot represent. **Falsifier:** that consumer
must copy an AEC contract or move consumer policy into AEC. **Revisit when:** the second
pilot inventories its required facts. **Expected result:** copied AEC contract files,
baseline measured before promotion, target `0`, unit `files`. **Owner:** repository owner.

### Semantic decision quality

| Choice | Quality | Risk | Reversibility | Maintainability | Scope |
|---|---|---|---|---|---|
| A. Structural core plus examples, outcomes, and bounded human review | Keeps claims matched to evidence | Medium review variation | High | Medium | Low |
| B. Add a closed deterministic quality rubric before human review | More consistent declarations if validated | Medium false-confidence risk | High | Medium-to-low as rubric grows | Medium |

**Recommendation:** A. **Evidence quality:** indirect (unmerged PR #140 experiment plus
directly verified outcome contracts). **Confidence:** medium. **Principal uncertainty:**
whether a closed rubric can discriminate useful advice without becoming another shape
check. **Falsifier:** a bounded corpus shows B rejects hollow decisions and accepts useful
ones more consistently. **Revisit when:** that corpus and review protocol exist.
**Expected result:** unsupported semantic-quality claims in release evidence, baseline
measured before promotion, target `0`, unit `claims`. **Owner:** repository owner.

### Learner adaptation

| Choice | Quality | Risk | Reversibility | Maintainability | Scope |
|---|---|---|---|---|---|
| A. Preserve one static register | Consistent but dense for some readers | Low product risk | Highest | High | None |
| B. Add optional local presentation variants | Potentially clearer while decisions stay fixed | Medium content-drift risk | High | Medium | Medium renderer/content change |

**Recommendation:** B after P0 and P1. **Evidence quality:** indirect (one pilot report
and open design work). **Confidence:** low. **Principal uncertainty:** whether variants
improve comprehension enough to justify maintenance. **Falsifier:** bounded user review
shows no improvement or any decision/card hash changes. **Revisit when:** G1-G5 are stable
and a review protocol exists. **Expected result:** hash differences across presentation
variants, baseline `0`, target `0`, unit `differences`. **Owner:** repository owner.

## Non-goals

- Executing code, procedures, reviews, merges, deployments, or releases.
- Inferring lifecycle movement from narration, labels, issue closure, or merge events.
- Becoming a project tracker, authoritative evidence collector, or competing state writer.
- Certifying that caller-supplied facts are true in the outside world.
- Guaranteeing semantic quality from schema or validator success.
- Automatic consumer upgrades, pin edits, pull-request merges, or deployments.
- Remote telemetry, learner surveillance, raw logs, or free-text outcome collection.
- Consumer-specific profiles, policy, secrets, repositories, or deployment rules in AEC.
- Publishing, paraphrasing, or adapting private course expression.
- Changing runtime or schema contracts as part of this documentation change.
- Adding a paid external service without a separate ROI and authority decision.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Human output omits validated facts | G1 golden, negative, and consumer rendering fixtures |
| Structural checks are mistaken for expert judgment | Explicit authorship language, falsifiers, observations, and bounded human review |
| Consumers copy framework contracts | Consolidated state/checkpoint path and consumer-specific probe |
| AEC becomes a hidden lifecycle writer | Pure-core capability checks and explicit ownership matrix |
| Fixed probes create false confidence | Label them framework fixtures and require consumer probes |
| Host wrappers drift | Rendered semantic parity tests, separate from loader parity |
| Outcome association is reported as causation | Closed evaluator vocabulary and required non-causal reporting |
| Learner adaptation changes engineering advice | Presentation-only variants with hash and semantic invariance tests |
| Release notification becomes automatic adoption | Keep `auto_merge_allowed=false`; consumer validates and pins |
| Private source expression leaks | Factual-only tracked provenance and exclusion from fixtures, logs, and CI |
| Review policy exceeds current enforcement | Treat unresolved high as blocking by policy and improve enforcement separately |

## Audit scope for this PRD

The 2026-10-09 source review covered the tracked repository, active architecture and
delivery documents, all current GitHub issue bodies in the supplied all-state export,
open pull-request metadata and implicated source, historical save states, local pilot and proof material, and ignored
private source documents. Git objects, caches, bytecode, operating-system metadata, and
other generated binaries were excluded because they are not product intent. No
untracked first-party document was present. Private expressive source material was read
only to check product coverage and remains local; this PRD contains independently stated
AEC requirements only.
