# Consumer Contract

AEC is reusable only when consumer-specific state stays in the consumer. AEC ships
no populated consumer profile; a consumer produces its own, shaped to the contract
validated by `tools/validate_foundation.py`.

The public state-provider boundary is the closed, versioned
[`consumer-state.schema.json`](../schemas/consumer-state.schema.json) contract. A caller
supplies one in-memory record plus the expected revision, expected environment, current
time, and AEC-owned procedure catalog. AEC performs no discovery or I/O at this seam.

This contract governs the runtime boundary between AEC and a consumer project. It is out
of scope for, and does not change, the separate repository-admission trust boundary that
gates source-changing pull requests into AEC itself: see
[handoff-reconciliation.md](handoff-reconciliation.md#what-exact_baseline-proves) for
what that boundary does and does not guarantee.

## AEC provides

- workflow and phase vocabulary;
- a deterministic resolution schema and hash contract;
- procedure-selection and evidence-policy contracts;
- course and upstream provenance;
- normalized mentoring-card data; and
- conformance fixtures and validators.

## Release discovery

Consumers discover reviewed updates through the official GitHub Release feed, not by
tracking AEC `main`. The attached `aec-release-manifest.json` binds the release tag,
exact Git revision, public contract versions, compatibility posture, and required
routine, material, and human-render probes. The adjacent
`release-manifest.schema.json` defines the closed asset shape.

The release asset is a candidate notification, not compatibility proof. A consumer owns
its scheduled check, update branch, pull request, detached install, validation, review,
merge, deployment, and rollback. An incompatible candidate must remain draft or blocked.
The manifest permanently declares `auto_merge_allowed=false`.

## The consumer provides

- repository instructions and a local procedure registry;
- current task, revision, environment, Lane, Phase, Gate, and evidence references;
- optional material-decision context with two or three choices, explicit tradeoffs,
  one recommendation, change-the-decision evidence, and the authority owner;
- agent adapters that only read and render the AEC decision;
- an authenticated single lifecycle writer;
- Project or issue projection rules;
- branch protection, review, merge, deployment, and rollback controls; and
- telemetry destinations and retention policy.

## Why the boundary sits here

AEC owns what is deterministic and repository-local: vocabulary, schemas, the hash
contract, and validators. The consumer owns what requires judgment against live state or
carries authority: what the task means, whether evidence is real, and what ships.

This is why AEC does not encode evidence collection, project projection, merge, or
deployment as built-in operations. Those steps change often, differ per consumer, and
must be reconciled against systems AEC does not read. A capability that needs live state
or carries release authority stays with the consumer even when AEC could compute it. The
exclusions under [Not wanted](operating-model.md#not-wanted) follow from that rule rather
than standing as independent prohibitions.

## Reference example

Consumer profiles live in consumer repositories, not in AEC. A reference
profile follows the shape validated by `tools/validate_foundation.py`: fields
`schema_version`, `project`, `profile_version`, `workflow`,
`lifecycle_authority: consumer-owned`, `aec_mode: read-only-mentor`, and
`agent_adapters: [...]` (non-empty list). AEC ships no populated profile. A
consumer produces its own and the AEC contract validates it in-place.

The resolver consumes that same profile object directly under `consumer_profile`.
Consumers must not translate it to an alternate `identity` and `version` shape.
The project value is the hashed consumer-profile identity, and `profile_version` is
the hashed consumer-profile revision.

Consumers must not vendor private course sources, infer a general Blueprint license
from AEC's recorded direct permission, create agent-specific policy forks, or let AEC
write their lifecycle state. Consumers may discover AEC's exact installed Blueprint
skills through the canonical `.agents/skills/` root or its Claude symlinks; they must
not silently fork or adapt those files.

## Pure consumer adapter

```python
from aec.consumer import ConsumerStateRejection, resolve_consumer_state

result = resolve_consumer_state(
    caller_state,
    procedure_catalog,
    current_time="2026-01-01T00:30:00Z",
    expected_environment="test",
    expected_revision="0123456789abcdef0123456789abcdef01234567",
)
if isinstance(result, ConsumerStateRejection):
    rejection = result.to_dict()  # card is always null
else:
    card = result.to_dict()
```

The record contains only project-neutral task, revision, environment, workflow
position, evidence, capability, procedure, policy, blocker, provider, freshness,
optional decision context, and read-only effect facts. Its `effects` object must
declare `executes=false` and `mutates=false`. The adapter rejects malformed or unknown
fields, stale freshness windows, revision or environment mismatches, effectful
declarations, and local private paths before invoking the resolver.

An accepted record is translated into the existing normalized resolver request. The
resulting card is versioned at `schema_version: 3.0.0` and contains Lane, Phase, the
stage and nine-phase rail position, Gate, rationale, required proof, Good, Finished, one
anti-example, and AEC-authored teaching. The teaching states the transferable lesson, why
the gate exists, and how to recognize the situation again.

The card also carries `card_hash`, computed at render time over the complete card except
`card_hash` itself. One closed validator covers every card field, checks that the card
agrees with itself, and recomputes the hash. That is local structural and tamper
integrity, not proof of origin: anyone who can rewrite a card can recompute the hash. AEC
adds no signing keys or secrets.

`decision_context` is optional and versioned at `schema_version: 2.0.0`. Omission means
the task has no material fork and the card returns `decision_support: null`. When
supplied, it must contain two or three choices. Every choice carries a lowercase
hyphenated identity an outcome receipt can cite exactly, and names quality, risk,
reversibility, maintainability, and scope tradeoffs. The recommendation must identify
one declared choice, explain why, name its principal uncertainty, declare a confidence,
declare one expected measurable result (a measure, a unit, a canonical integer baseline
and target, a direction that agrees with those numbers, and a readable threshold), and
name observable evidence that would justify revisiting it. `context.revision` must equal the
record revision, and
`context.evidence_quality` must support the declared confidence. The authority owner is
one of `agent`, `consumer-owner`, or `external`; AEC itself is never an authority owner.
A context missing any of those facts is rejected before a card is rendered.

The complete decision context is normalized, bound into the request hash, copied to
the decision, and rendered identically on the public card. Its transition request is a
draft with `authoritative=false`, `executes=false`, and `mutates=false`. AEC never
submits that draft or acts on the recommendation.

**`decision_support` is a validated pass-through of the submitted `decision_context`, not
AEC-derived analysis.** AEC checks the submitted context for completeness and internal
consistency — schema shape, revision match, and the evidence-quality-to-confidence bound
above — and rejects it outright if any required fact is missing. It does not select,
score, or rank the choices, and it does not add or alter recommendation content. What
the card renders as `decision_support` is structurally identical to what the consumer
submitted as `decision_context` — every field and value unchanged, independent of
incidental JSON formatting such as key order or whitespace, which the canonical
serialization normalizes. The resolver validates and republishes the decoded structure
bound to the card hash; it does not evaluate the options.

A consumer that acted on a rendered recommendation may later write one local outcome
record holding the card, the carried decision snapshot, and one receipt binding that
snapshot to what was observed. Verification validates the snapshot, recomputes its
resolution hash, and reproduces the card from it before reading any receipt fact. This
proves internal consistency, not trusted authorship or origin. Receipts are never
uploaded, aggregated remotely, or fed back into policy. See
[decision outcomes](architecture/decision-outcomes.md) for the receipt contract, the
derived verdict rules, and the local evaluator.

### Versioned transition

The unversioned decision context that shipped before this contract is no longer
accepted: it cannot state evidence quality, confidence, principal uncertainty, or an
expected measurable result, so its recommendation could never be compared with a real
outcome. Records without `decision_context` are unaffected, and every other consumer
state, request, and decision version is unchanged. To migrate, add `schema_version`,
`context`, and the four new `recommendation` fields.

The public card moved from `2.0.0` to `3.0.0` in the same transition, because `card_hash`
is a new required field. A reader that pinned the `2.0.0` card shape must accept
`card_hash` and should recompute it. Consumer state remains at `1.0.0`.

## Connection proof

A pin bump that tightens a contract is not always visible from a routine check. The
`d35f535` transition above tightened `decision_context` strictly; a routine probe that
never supplies `decision_context` still passes, so a consumer that only exercises the
routine path learns nothing about the break until a material-decision card goes red.

Before attempting any real coaching against a pinned AEC checkout, run the connection
proof from the AEC repository root:

```bash
python3.12 -m tools.validate_consumer_connection --self-check
```

This resolves a ROUTINE probe (no `decision_context`) and a MATERIAL probe (a closed
`decision_context`) through the same pure adapter every consumer uses,
`aec.consumer.resolve_consumer_state`. Both must resolve to a non-authoritative card for
the proof to report `PASS`. `--self-check` additionally resolves
`tests/fixtures/consumer-connection/previous-contract.json`, a fixture pinned to the
pre-`d35f535` `decision_context` shape, and asserts it is rejected before any card is
rendered. A rejection names the exact fields the consumer's own state is missing or must
change, for example `decision_context is missing required fields: context,
schema_version` and `decision_context.recommendation is missing required fields:
confidence, expected_result, principal_uncertainty` -- not a generic failure. See
`tools/validate_consumer_connection.py` for the field-level diagnosis this proof runs
beyond what `resolve_consumer_state` itself reports.

## Conformance exit gate

The consumer integration is ready for a bounded pilot only when:

1. both real agent loaders discover the intended local procedure set exactly once;
2. the same input produces the same normalized AEC decision and hash;
3. missing, stale, malformed, duplicate, and effectful inputs fail closed;
4. one real issue traverses the nine phases with exact evidence; and
5. the authoritative record and visible project projection reconcile.

The consumer integration and ownership disposition for the first FedJobAdvisor
consumer is recorded in the
[FedJobAdvisor migration map](history/fedjobadvisor-migration-map.md). That map is evidence and
does not import its transport, Project, label, writer, or deployment implementation
into AEC. The migration it records is finished — all eleven source issues are closed —
so the map is retained as a historical audit artifact, not a live work list.
